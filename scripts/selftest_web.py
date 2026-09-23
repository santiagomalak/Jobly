"""Prueba la app web y la capa Turso sin internet ni claves reales.

  python scripts/selftest_web.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.pop("TURSO_DATABASE_URL", None)
os.environ.pop("TURSO_AUTH_TOKEN", None)
os.environ.pop("VERCEL", None)

from radar import db, llm  # noqa: E402
from radar.models import Ticket  # noqa: E402
from radar.store import Store  # noqa: E402
from radar.web import create_app  # noqa: E402

OK = llm.LLMResult("Respuesta de prueba lista para copiar.", "test")


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)
    print(f"  ok  {msg}")


def test_turso_adapter() -> None:
    print("Turso (HTTP mockeado)")
    resp = MagicMock()
    resp.raise_for_status = lambda: None
    resp.json.return_value = {
        "results": [
            {"type": "ok", "response": {"type": "execute", "result": {
                "cols": [{"name": "n"}, {"name": "t"}, {"name": "x"}],
                "rows": [[{"type": "integer", "value": "7"}, {"type": "text", "value": "hola"}, {"type": "null"}]],
            }}},
            {"type": "ok", "response": {"type": "close"}},
        ]
    }
    conn = db.TursoConnection("libsql://mi-db-org.turso.io", "tok")
    with patch("radar.db.requests.post", return_value=resp) as post:
        fila = conn.execute("SELECT ?, ?, ?", (5, "a", None)).fetchone()
        url = post.call_args.args[0]
        body = post.call_args.kwargs["json"]
        headers = post.call_args.kwargs["headers"]
    check(url == "https://mi-db-org.turso.io/v2/pipeline", "libsql:// se convierte a https:// /v2/pipeline")
    check(headers["Authorization"] == "Bearer tok", "envía el token como Bearer")
    check(body["requests"][0]["stmt"]["args"][0] == {"type": "integer", "value": "5"}, "entero codificado como string")
    check(body["requests"][0]["stmt"]["args"][2] == {"type": "null"}, "None codificado como null")
    check(body["requests"][-1] == {"type": "close"}, "cierra el pipeline")
    check((fila["n"], fila["t"], fila["x"]) == (7, "hola", None), "decodifica filas por nombre")
    resp.json.return_value = {"results": [{"type": "error", "error": {"message": "boom"}}]}
    with patch("radar.db.requests.post", return_value=resp):
        try:
            conn.execute("SELECT 1")
            check(False, "un error de Turso debe levantar excepción")
        except RuntimeError as exc:
            check("boom" in str(exc), "propaga el mensaje de error de Turso")


def test_fuentes() -> None:
    print("Fuentes (HTTP mockeado)")
    from radar import sources

    def resp(data, status=200):
        m = MagicMock()
        m.status_code = status
        m.json.return_value = data
        m.raise_for_status = lambda: None
        return m

    ahora = 1790185103
    hima = {"jobs": [
        {"title": "n8n Developer", "guid": "g1", "applicationLink": "https://himalayas.app/j/1", "pubDate": ahora,
         "employmentType": "Contractor", "locationRestrictions": [], "seniority": ["Mid-level"],
         "description": "<p>Build workflows</p>", "minSalary": None},
        {"title": "Data Engineer", "guid": "g2", "applicationLink": "https://himalayas.app/j/2", "pubDate": ahora,
         "employmentType": "Full Time", "locationRestrictions": ["Argentina"], "seniority": ["Senior", "Manager"],
         "description": "x", "minSalary": 90000, "maxSalary": 120000, "currency": "USD", "salaryPeriod": "annual"},
        {"title": "Viejo", "guid": "g3", "applicationLink": "https://himalayas.app/j/3", "pubDate": 1000,
         "employmentType": "Full Time", "locationRestrictions": [], "seniority": [], "description": "x"},
    ]}
    cfg = {"http_timeout": 5, "user_agent": "t", "_src": {"queries": ["n8n", "data"], "params": {"worldwide": "true"}}}
    with patch("radar.sources.requests.get", return_value=resp(hima)) as g, patch("radar.sources.time.sleep"):
        tks = sources.fetch_himalayas("himalayas-x", "", cfg)
        params = g.call_args_list[0].kwargs["params"]
    check(len(tks) == 2, "Himalayas: deduplica entre consultas y descarta avisos viejos")
    check(params == {"worldwide": "true", "q": "n8n"}, "Himalayas: manda params comunes + q")
    a = next(t for t in tks if t.title == "n8n Developer")
    check("tipo:contract" in a.tags and "ubicacion:Worldwide" in a.tags, "Himalayas: contractor y ubicación vacía = mundial")
    b = next(t for t in tks if t.title == "Data Engineer")
    check("ubicacion:Argentina" in b.tags and "seniority:Senior" in b.tags, "Himalayas: ubicación y seniority como etiquetas")
    check(any(t.startswith("salario:") for t in b.tags) and b.raw_budget == "", "Himalayas: el sueldo va a etiquetas, no a presupuesto")

    with patch("radar.sources.requests.get", return_value=resp({}, status=429)), patch("radar.sources.time.sleep"):
        check(sources.fetch_himalayas("h", "", cfg) == [], "Himalayas: ante 429 corta sin romper")

    post_reddit = {"data": {"children": [{"data": {
        "title": "[HIRING] n8n automation", "permalink": "/r/forhire/comments/x/", "selftext": "budget $300",
        "created_utc": time.time() - 60, "link_flair_text": "Hiring"}}]}}
    url_r = "https://www.reddit.com/r/forhire/new.json?limit=100"
    cfg_r = {"http_timeout": 5, "user_agent": "ua"}
    sources._reddit_token.update(valor="", expira=0.0)
    with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "sec"}), \
         patch("radar.sources.requests.post", return_value=resp({"access_token": "tok", "expires_in": 86400})) as pt, \
         patch("radar.sources.requests.get", return_value=resp(post_reddit)) as gt:
        rt = sources.fetch_reddit("reddit-forhire", url_r, cfg_r)
        destino, hdrs = gt.call_args.args[0], gt.call_args.kwargs["headers"]
    check(pt.call_args.kwargs["auth"] == ("id", "sec"), "Reddit: pide token OAuth con las credenciales de la app")
    check(destino.startswith("https://oauth.reddit.com/r/forhire/new?") and hdrs["Authorization"] == "bearer tok", "Reddit: con token usa oauth.reddit.com")
    check(len(rt) == 1 and rt[0].title.startswith("[HIRING]"), "Reddit: devuelve los [HIRING]")
    sources._reddit_token.update(valor="", expira=0.0)
    with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""}), \
         patch("radar.sources.requests.get", return_value=resp(post_reddit)) as gt:
        sources.fetch_reddit("reddit-forhire", url_r, cfg_r)
        check(gt.call_args.args[0] == url_r and "Authorization" not in gt.call_args.kwargs["headers"], "Reddit: sin credenciales prueba el JSON público")

    jobi = {"jobs": [{"id": 1, "jobTitle": "Ops", "url": "https://jobicy.com/j/1", "jobType": ["Contract"],
                      "jobGeo": "Anywhere", "jobLevel": "Junior", "jobDescription": "<b>desc</b>", "pubDate": "2026-09-20"}]}
    with patch("radar.sources.requests.get", return_value=resp(jobi)), patch("radar.sources.time.sleep"):
        j = sources.fetch_jobicy("jobicy", "", {"http_timeout": 5, "user_agent": "t", "_src": {"queries": [{"geo": "latam"}]}})
    check(j[0].tags[:3] == ["tipo:contract", "ubicacion:Anywhere", "seniority:Junior"], "Jobicy: etiquetas de tipo, ubicación y nivel")


def test_fit_y_paralelo() -> None:
    print("Encaje y recolección")
    from radar import fit, sources
    from radar.memory import Memory

    mem = Memory(Path(__file__).resolve().parent.parent / "memoria")
    t = Ticket(source="x", title="Data role", url="https://e.com/f", description="We need python, kubernetes and 5+ years of experience with dbt.")
    enc = fit.analizar(t, mem)
    check("python" in enc.tenes and "dbt" in enc.tenes, "encaje: lo que pide y ya tenés")
    check("kubernetes" in enc.faltan, "encaje: lo que pide y no figura en tu perfil")
    check(enc.anios == 5, "encaje: años exigidos")

    orden: list[str] = []

    def falso(name, url, cfg):
        orden.append(name)
        if name == "rota":
            raise RuntimeError("boom")
        return [Ticket(source=name, title=name, url=f"https://e.com/{name}")]

    fuentes = [{"name": n, "type": "falso"} for n in ("a", "rota", "b")] + [{"name": "apagada", "type": "falso", "enabled": False}]
    with patch.dict(sources.FETCHERS, {"falso": falso}):
        tks, errores = sources.collect(fuentes, {})
    check([x.title for x in tks] == ["a", "b"], "collect en paralelo: conserva el orden de sources.yaml")
    check(len(errores) == 1 and "rota" in errores[0], "collect: una fuente rota no tumba las demás")
    check("apagada" not in orden, "collect: las fuentes deshabilitadas no corren")


def test_store(path: Path) -> None:
    print("Store")
    s = Store(path)
    t = Ticket(source="x", title="n8n bot", url="https://e.com/1", description="d", module="AUTOMATION", score=60, verdict="pass")
    s.save(t)
    s.marcar(t.fingerprint, "postulado")
    s.set_notas(t.fingerprint, "llamar el lunes")
    t.score = 70
    s.save(t)  # un re-guardado no puede pisar estado ni notas
    row = s.get(t.fingerprint)
    check(row["estado"] == "postulado" and row["notas"] == "llamar el lunes", "upsert conserva estado y notas")
    check(row["score"] == 70, "upsert actualiza el score")
    check(row["postulado_at"] is not None, "marcar guarda la fecha de postulación")
    m = s.metricas(5, 900)
    check(m["enviadas_7d"] == 1 and m["racha_dias"] == 1, "métricas: 1 enviada esta semana, racha de 1 día")
    try:
        s.marcar(t.fingerprint, "inventado")
        check(False, "un estado inválido debe fallar")
    except ValueError:
        check(True, "rechaza estados inválidos")

    def hace(dias: int) -> None:
        s.conn.execute("UPDATE tickets SET postulado_at = datetime('now', ?) WHERE fingerprint = ?",
                       (f"-{dias} days", t.fingerprint))
        s.conn.commit()

    check(s.seguimientos_pendientes() == [], "recién postulado: no hay seguimiento")
    hace(3)
    due = s.seguimientos_pendientes()
    check(len(due) == 1 and due[0][1] == 1, "a las 48 h vence el seguimiento 1")
    s.registrar_seguimiento(t.fingerprint)
    check(s.seguimientos_pendientes() == [], "tras el 1º, el 2º recién vence a los 6 días")
    hace(7)
    check(s.seguimientos_pendientes()[0][1] == 2, "a los 6 días vence el seguimiento 2")
    s.registrar_seguimiento(t.fingerprint)
    check(s.registrar_seguimiento(t.fingerprint) == 2 and s.seguimientos_pendientes() == [], "máximo 2 seguimientos")
    s.marcar(t.fingerprint, "respondido")
    hace(30)
    check(s.seguimientos_pendientes() == [], "si respondieron, no se persigue")
    s.close()


def test_notify() -> None:
    print("Discord")
    from radar import notify

    enviados: list[dict] = []
    t = Ticket(source="x", title="@everyone n8n", url="https://e.com/9", description="@everyone mirá", pitch="carta")
    os.environ["JOBLY_URL"] = "https://jobly.example.app/"
    try:
        with patch("radar.notify.post", side_effect=lambda w, p: enviados.append(p) or True):
            notify.send_ticket("hook", t)
    finally:
        os.environ.pop("JOBLY_URL", None)
    check(all(p["allowed_mentions"] == {"parse": []} for p in enviados), "un aviso de terceros no puede mencionar @everyone")
    check(f"https://jobly.example.app/ticket/{t.fingerprint}" in enviados[1]["content"], "la alerta trae el link directo al CRM")


def test_web(path: Path) -> None:
    print("Web")
    os.environ["JOBLY_PASSWORD"] = "clave-de-prueba"
    app = create_app(db_path=path)
    c = app.test_client()

    r = c.get("/healthz")
    check(r.status_code == 200, "/healthz responde sin login")
    r = c.get("/manifest.webmanifest")
    check(r.status_code == 200 and r.json["display"] == "standalone", "el manifest de la app es público")
    r = c.get("/icon-192.png")
    check(r.status_code == 200 and r.data[:4] == bytes([137]) + b"PNG", "el ícono PNG es público")
    check(c.get("/icon-100.png").status_code == 404, "solo hay íconos de 192 y 512")
    r = c.get("/")
    check(r.status_code == 302 and "/login" in r.headers["Location"], "sin sesión redirige a /login")
    r = c.post("/api/marcar", json={})
    check(r.status_code == 401, "la API sin sesión da 401")
    r = c.post("/login", data={"password": "mala"})
    check(r.status_code == 401, "contraseña incorrecta rechazada")
    r = c.post("/login", data={"password": "clave-de-prueba"})
    check(r.status_code == 302, "contraseña correcta entra")
    r = c.get("/")
    check(r.status_code == 200 and b"Pipeline" in r.data, "el pipeline carga con sesión")
    check(r.headers.get("X-Robots-Tag", "").startswith("noindex"), "cabecera noindex presente")
    check(r.headers.get("X-Frame-Options") == "DENY", "anti-clickjacking presente")

    r = c.post("/api/marcar", data="fingerprint=x", content_type="application/x-www-form-urlencoded")
    check(r.status_code == 415, "un POST que no es JSON se rechaza (anti-CSRF)")

    with patch("radar.llm.generate", return_value=OK):
        r = c.post("/api/ticket", json={
            "url": "https://example.com/job/1", "title": "Bot de WhatsApp",
            "description": "Necesitamos un workflow n8n con webhook que sincronice el CRM con WhatsApp. " * 2,
            "budget": "USD 300", "modulo": "auto"})
        check(r.status_code == 200 and r.json["ok"], "carga manual de una oferta")
        fp = r.json["fingerprint"]
        r2 = c.post("/api/ticket", json={"url": "https://example.com/job/1", "description": "x" * 40})
        check(r2.json.get("existente") is True, "no duplica una oferta ya cargada")

        r = c.post("/api/ticket", json={"url": "javascript:alert(1)", "description": "x" * 40})
        check(r.status_code == 400, "rechaza URLs que no son http(s)")
        r = c.post("/api/ticket", json={"url": "https://example.com/2", "description": "algo totalmente sin keywords conocidas " * 3})
        check(r.status_code == 422 and r.json["necesita_modulo"], "pide módulo si no puede detectarlo")

        r = c.get(f"/ticket/{fp}")
        check(r.status_code == 200 and b"Respuesta de prueba" in r.data, "el detalle muestra el pitch")
        check(b"Abrir postulaci" in r.data, "el detalle tiene el botón de postulación")
        check(b"Encaje con tu perfil" in r.data, "el detalle muestra el encaje con tu perfil")
        an = c.get("/analitica")
        check(an.status_code == 200 and "Ritmo semanal" in an.get_data(as_text=True), "la pantalla de analítica carga")
        check(c.get("/ticket/../../etc/passwd").status_code == 404, "fingerprint inválido da 404")

        r = c.post("/api/marcar", json={"fingerprint": fp, "estado": "postulado"})
        check(r.status_code == 200, "marcar como postulado")
        check(c.post("/api/marcar", json={"fingerprint": fp, "estado": "hackeado"}).status_code == 400, "estado inválido rechazado")
        check(c.post("/api/notas", json={"fingerprint": fp, "notas": "hola"}).status_code == 200, "guardar notas")
        r = c.post("/api/pitch", json={"fingerprint": fp})
        check(r.status_code == 200 and r.json["engine"] == "test", "regenerar pitch")

        s2 = Store(path)
        s2.conn.execute("UPDATE tickets SET postulado_at = datetime('now', '-3 days') WHERE fingerprint = ?", (fp,))
        s2.conn.commit()
        s2.close()
        check(b"Seguimiento 1 vencido" in c.get(f"/ticket/{fp}").data, "el detalle avisa el seguimiento vencido")
        check(b"seguimiento 1" in c.get("/").data, "el pipeline lista el seguimiento pendiente")
        r = c.post("/api/seguimiento", json={"fingerprint": fp})
        check(r.status_code == 200 and r.json["numero"] == 1, "genera el seguimiento 1")
        c.post("/api/seguimiento_hecho", json={"fingerprint": fp})
        c.post("/api/seguimiento_hecho", json={"fingerprint": fp})
        check(c.post("/api/seguimiento", json={"fingerprint": fp}).status_code == 400, "no hay tercer seguimiento")

        r = c.post("/api/ask", json={"pregunta": "¿Qué frameworks usás?", "max_chars": 300})
        check(r.status_code == 200 and r.json["text"], "el asistente responde")
        check(c.post("/api/ask", json={"pregunta": "  "}).status_code == 400, "pregunta vacía rechazada")
        check(c.post("/api/ask", json={"pregunta": "x", "max_chars": 9}).status_code == 400, "tope fuera de rango rechazado")

    csv_texto = "url\ttitle\tdescription\nhttps://e.com/a\tScraper\tweb scraping con playwright, presupuesto $200\nnotaurl\tX\ty\n"
    r = c.post("/api/importar", json={"csv": csv_texto})
    check(r.status_code == 200 and r.json["nuevos"] == 1, "importa filas pegadas (TSV) y descarta URLs inválidas")
    check(c.post("/api/importar", json={"csv": "titulo,descripcion\na,b"}).status_code == 400, "CSV sin columna url rechazado")

    s = Store(path)
    s.save(Ticket(source="x", title="Malicioso", url="javascript:alert(1)", description="d",
                  module="WEB", score=60, verdict="pass"))
    s.close()
    html = c.get("/").data.decode()
    check('href="javascript:' not in html, "una URL javascript: nunca llega a un href")

    check(c.post("/logout").status_code == 302 and c.get("/").status_code == 302, "logout cierra la sesión")

    print("Falla cerrada")
    os.environ["JOBLY_PASSWORD"] = ""
    sin = create_app(db_path=path).test_client()
    check(sin.get("/").status_code == 503, "sin JOBLY_PASSWORD la app no responde")
    check(sin.get("/healthz").status_code == 200, "salvo el healthcheck")
    os.environ["JOBLY_PASSWORD"] = "clave-de-prueba"
    os.environ["VERCEL"] = "1"
    try:
        r = create_app(db_path=path).test_client().get("/login")
        check(r.status_code == 503, "en Vercel sin Turso no arranca (el disco no persiste)")
    finally:
        os.environ.pop("VERCEL", None)


def main() -> int:
    test_turso_adapter()
    test_fuentes()
    test_notify()
    test_fit_y_paralelo()
    with tempfile.TemporaryDirectory() as tmp:
        test_store(Path(tmp) / "a.sqlite")
        test_web(Path(tmp) / "b.sqlite")
    print("\n✅ selftest_web OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
