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

if hasattr(sys.stdout, "reconfigure"):  # consola de Windows (cp1252) y emojis
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

#  pop() no alcanza: radar.config hace load_dotenv() al importarse (recién cuando se
#  importa radar.web más abajo) y, como no sobreescribe variables ya presentes, una
#  variable *ausente* la repone desde el .env real — reconectando este test a la Turso
#  de producción sin que nada lo avise. Dejarlas en "" sí cuenta como "presente".
os.environ["TURSO_DATABASE_URL"] = ""
os.environ["TURSO_AUTH_TOKEN"] = ""
os.environ["VERCEL"] = ""

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
    with patch("radar.db.requests.Session.post", return_value=resp) as post:
        fila = conn.execute("SELECT ?, ?, ?", (5, "a", None)).fetchone()
        url = post.call_args.args[0]
        body = post.call_args.kwargs["json"]
    check(url == "https://mi-db-org.turso.io/v2/pipeline", "libsql:// se convierte a https:// /v2/pipeline")
    check(conn._http.headers["Authorization"] == "Bearer tok", "envía el token como Bearer")
    check(db.TursoConnection("libsql://mi-db-org.turso.io", "tok")._http is conn._http, "reutiliza la sesión HTTP (sin handshake por consulta)")
    check(body["requests"][0]["stmt"]["args"][0] == {"type": "integer", "value": "5"}, "entero codificado como string")
    check(body["requests"][0]["stmt"]["args"][2] == {"type": "null"}, "None codificado como null")
    check(body["requests"][-1] == {"type": "close"}, "cierra el pipeline")
    check((fila["n"], fila["t"], fila["x"]) == (7, "hola", None), "decodifica filas por nombre")
    resp.json.return_value = {"results": [{"type": "error", "error": {"message": "boom"}}]}
    with patch("radar.db.requests.Session.post", return_value=resp):
        try:
            conn.execute("SELECT 1")
            check(False, "un error de Turso debe levantar excepción")
        except RuntimeError as exc:
            check("boom" in str(exc), "propaga el mensaje de error de Turso")

    # Transacción: BEGIN + pasos condicionados + COMMIT/ROLLBACK en un solo request
    resp.json.return_value = {"results": [{"type": "ok", "response": {"type": "batch", "result": {
        "step_results": [None, {"cols": [], "rows": []}, None, None, None],
        "step_errors": [None, None, {"message": "UNIQUE constraint failed"}, None, None]}}}]}
    with patch("radar.db.requests.Session.post", return_value=resp) as post:
        try:
            conn.transaccion([("INSERT INTO t VALUES (?)", (1,)), ("INSERT INTO t VALUES (?)", (1,))])
            check(False, "un paso fallido debe levantar excepción")
        except RuntimeError as exc:
            check("UNIQUE" in str(exc), "transacción: un paso que falla levanta el error")
        pasos = post.call_args.kwargs["json"]["requests"][0]["batch"]["steps"]
    check(pasos[0]["stmt"]["sql"] == "BEGIN" and pasos[-2]["stmt"]["sql"] == "COMMIT"
          and pasos[-1]["condition"]["type"] == "not", "transacción: BEGIN … COMMIT y ROLLBACK si algo falla")
    check(all(p["condition"] == {"type": "ok", "step": i} for i, p in enumerate(pasos[1:-1])),
          "transacción: cada paso depende de que el anterior haya salido bien")


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
    feed_reddit = MagicMock(status=200, bozo=0, headers={}, entries=[
        MagicMock(title="[HIRING] n8n automation", link="https://www.reddit.com/r/forhire/comments/x/",
                  summary="<p>budget $300</p> submitted by <a>/u/alguien</a> [link] [comments]",
                  published="2026-10-05T12:00:00+00:00", published_parsed=time.gmtime(), updated_parsed=None),
        MagicMock(title="[For Hire] dev", link="https://www.reddit.com/r/forhire/comments/y/", summary="",
                  published="", published_parsed=time.gmtime(), updated_parsed=None)])
    with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""}), \
         patch("radar.sources.requests.get") as gt, \
         patch("radar.sources.feedparser.parse", return_value=feed_reddit) as fp:
        rr = sources.fetch_reddit("reddit-forhire", url_r, cfg_r)
    check(fp.call_args.args[0] == "https://www.reddit.com/r/forhire/new/.rss?limit=100" and not gt.called, "Reddit: sin credenciales lee el feed RSS público")
    check(len(rr) == 1 and rr[0].description == "budget $300", "Reddit RSS: solo los [HIRING] y sin la cola 'submitted by'")
    with patch.dict(os.environ, {"REDDIT_CLIENT_ID": "", "REDDIT_CLIENT_SECRET": ""}), \
         patch("radar.sources.feedparser.parse", return_value=MagicMock(status=403, bozo=0, headers={}, entries=[])):
        try:
            sources.fetch_reddit("reddit-forhire", url_r, cfg_r)
            bloqueado = False
        except RuntimeError:
            bloqueado = True
    check(bloqueado, "Reddit RSS: un 403 se informa como error de la fuente")

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


def test_crm(path: Path) -> None:
    print("CRM: migraciones, etapas, importador, score, meta")
    import json as _json

    from radar import copiloto, importador, migraciones
    from radar.config import load_config
    from radar.memory import Memory
    from radar import fit

    s = Store(path)
    cols_antes = [r["name"] for r in s.conn.execute("PRAGMA table_info(tickets)").fetchall()]
    check(migraciones.version_actual(s.conn) == 1 and "etapa" in cols_antes, "la migración 0001 se aplica sola al abrir la base")
    migraciones.revertir(s.conn, 0)
    cols_down = [r["name"] for r in s.conn.execute("PRAGMA table_info(tickets)").fetchall()]
    check("etapa" not in cols_down and "costo_usd" in cols_down, "migrate --down 0 deja el esquema anterior")
    migraciones.aplicar(s.conn)
    check([r["name"] for r in s.conn.execute("PRAGMA table_info(tickets)").fetchall()] == cols_antes, "y volver a subir deja el esquema idéntico")

    # Descartar no es postular (bug: "perdido" desde "nuevo" contaba como enviada)
    a = Ticket(source="x", title="Descartable", url="https://e.com/d", description="d", module="WEB", score=60, verdict="pass")
    b = Ticket(source="x", title="Postulable", url="https://e.com/p", description="d", module="WEB", score=60, verdict="pass")
    s.save_many([(a, False), (b, False)])
    s.mover(a.fingerprint, "descartada")
    s.marcar(b.fingerprint, "postulado")
    m = s.metricas(5, 900)
    check(m["enviadas_total"] == 1 and s.get(a.fingerprint)["postulado_at"] is None, "descartar no suma una postulación enviada")
    s.marcar(b.fingerprint, "perdido")
    check(s.get(b.fingerprint)["etapa"] == "rechazada", "perdido después de postular = rechazada")
    eventos = s.detalle(b.fingerprint)["eventos"]
    check([e["a_etapa"] for e in eventos][:2] == ["rechazada", "postulada"], "cada cambio de etapa queda en la timeline")
    c = Ticket(source="x", title="Seguir", url="https://e.com/s", description="d", module="WEB", score=60, verdict="pass")
    s.save(c)
    s.mover(c.fingerprint, "postulada")
    check(s.get(c.fingerprint)["proxima_accion"] == "Seguimiento 1", "al postular se agenda el seguimiento 1")
    s.conn.execute("UPDATE tickets SET postulado_at = datetime('now', '-20 days'), seguimientos = 2 WHERE fingerprint = ?", (c.fingerprint,))
    check(s.cerrar_sin_respuesta() == 1 and s.get(c.fingerprint)["etapa"] == "sin_respuesta", "2 seguimientos sin respuesta: se cierra sola")

    # Importador
    cfg = load_config()
    mem = Memory(Path(cfg["root"]) / cfg["memory_dir"])
    imp = importador.Importacion(s, cfg, mem.taxonomia(), fit.texto_perfil(mem))
    filas = [{"titulo": f"Workflow n8n {i}", "empresa_o_cliente": f"Cliente {i}", "url": f"https://www.workana.com/job/{i}?utm_source=x",
              "tipo": "freelance", "presupuesto_min": "200", "moneda": "USD", "periodo_pago": "proyecto"} for i in range(270)]
    filas += [{"titulo": "Sin url", "url": "nope"}] * 10
    filas += [dict(f, url=f["url"].replace("www.", "").split("?")[0] + "/") for f in filas[:20]]  # duplicados por URL
    iid = imp.crear("workana", "ignorar", {"title": "titulo"})
    total = {"creadas": 0, "ignoradas": 0, "errores": 0}
    for i in range(0, len(filas), importador.MAX_CHUNK):
        r = imp.chunk(iid, filas[i:i + importador.MAX_CHUNK], i)
        total["creadas"] += r["creadas"]
        total["ignoradas"] += r["ignoradas"]
        total["errores"] += len(r["errores"])
    check(total == {"creadas": 270, "ignoradas": 20, "errores": 10}, "300 filas: 270 nuevas, 20 duplicadas, 10 errores sin abortar")
    check(importador.mapeo_guardado(s.conn, "workana") == {"title": "titulo"}, "el mapeo de columnas queda guardado por fuente")
    antes = s.conn.execute("SELECT COUNT(*) AS n FROM tickets").fetchone()["n"]
    r = imp.deshacer(iid)
    despues = s.conn.execute("SELECT COUNT(*) AS n FROM tickets").fetchone()["n"]
    check(r["borradas"] == 270 and antes - despues == 270, "deshacer el lote borra lo que creó")
    v, _ = importador.validar({"titulo": "x", "url": "https://e.com/q", "notas": "'=HYPERLINK(1)"}, "f")
    check(v.extra["notas"] == "=HYPERLINK(1)", "el apóstrofo anti-fórmula del prompt se limpia al importar")

    # Score de oportunidad
    from radar.oportunidad import calcular
    perfil = fit.texto_perfil(mem)
    bueno, _ = importador.validar({"titulo": "Automatizar reportes con n8n", "url": "https://w.com/1", "tipo": "freelance",
                                   "presupuesto_min": "300", "moneda": "USD", "periodo_pago": "proyecto", "duracion_estimada": "2",
                                   "stack": "n8n | python", "cliente_verificado": "si", "proyectos_previos_cliente": "6",
                                   "calificacion_cliente": "4.9", "idioma": "es"}, "w")
    malo, _ = importador.validar({"titulo": "Senior Platform Engineer", "url": "https://w.com/2", "tipo": "empleo",
                                  "pais": "USA only", "seniority": "senior", "stack": "scala | kafka | kubernetes",
                                  "requisitos": "fluent English, 8+ years", "idioma": "en"}, "w")
    check(calcular(bueno, perfil, cfg)[0] > 80, "proyecto de USD 300 en 2 días con cliente verificado: score > 80")
    check(calcular(malo, perfil, cfg)[0] < 30, "senior restringido a EE. UU. con inglés hablado: score < 30")

    # Meta: ingreso cargado + pipeline ponderado
    s.agregar_ingreso(b.fingerprint, 300, "cobrado", (copiloto.et.ahora_art()).date().isoformat())
    t = s.tablero(cfg)
    meta = copiloto.meta(t, cfg)
    check(meta["cobrado"] == 300 and meta["pct_confirmado"] == 33, "un cobro de USD 300 llena un tercio de la meta")
    check(meta["falta"] > 0 and meta["por_dia"] >= 1, "calcula cuántas propuestas por día faltan")
    s.close()


def test_web_crm(path: Path) -> None:
    print("Web: CRM nuevo")
    os.environ["JOBLY_PASSWORD"] = "clave-de-prueba"
    c = create_app(db_path=path).test_client()
    for _ in range(10):
        c.post("/login", data={"password": "mala"}, headers={"X-Real-IP": "9.9.9.9"})
    r = c.post("/login", data={"password": "clave-de-prueba"}, headers={"X-Real-IP": "9.9.9.9"})
    check(r.status_code == 429, "10 fallos desde la misma IP: bloqueo temporal (429)")
    r = c.post("/login", data={"password": "clave-de-prueba"}, headers={"X-Real-IP": "8.8.8.8"})
    check(r.status_code == 302, "otra IP entra normal")

    r = c.post("/api/importaciones", json={"fuente": "upwork", "politica": "ignorar", "mapeo": {"Title": "titulo", "x": "hack"}})
    iid = r.json["id"]
    fila = {"titulo": "=cmd|' /C calc'!A0", "url": "https://upwork.com/jobs/1", "tipo": "freelance",
            "presupuesto_min": "250", "empresa_o_cliente": "Acme", "duracion_estimada": "3"}
    r = c.post(f"/api/importaciones/{iid}/chunk", json={"filas": [fila, {"titulo": "x", "url": "mal"}]})
    check(r.status_code == 200 and r.json["creadas"] == 1 and len(r.json["errores"]) == 1, "la API del importador crea y reporta errores por fila")
    check(c.post(f"/api/importaciones/{iid}/chunk", json={"filas": [fila] * 101}).status_code == 400, "más de 100 filas por envío se rechaza")
    check(c.get("/api/mapeo?fuente=upwork").json["mapeo"] == {"Title": "titulo"}, "el mapeo guardado ignora campos inventados")
    check(b"#" in c.get("/importar").data and b"upwork" in c.get("/importar").data, "el historial de importaciones se ve")

    home = c.get("/").get_data(as_text=True)
    check("confirmados" in home and "por día" in home, "la home muestra la barra de meta y las propuestas por día")
    check("★" in home, "la home ordena por score de oportunidad")

    csv_txt = c.get("/exportar.csv").get_data(as_text=True)
    check("'=cmd" in csv_txt and "\n=cmd" not in csv_txt, "el export CSV neutraliza fórmulas (CSV injection)")

    s = Store(path)
    fp = s.get_by_url("https://upwork.com/jobs/1")["fingerprint"]
    s.close()
    check(c.post("/api/etapa", json={"fingerprint": fp, "etapa": "inventada"}).status_code == 400, "etapa inválida rechazada")
    r = c.post("/api/etapa", json={"fingerprint": fp, "etapa": "postulada"})
    check(r.json["proxima_accion"] == "Seguimiento 1", "postular desde la API agenda el seguimiento")
    check(c.post("/api/accion", json={"fingerprint": fp, "texto": "Llamar", "fecha": "mal"}).status_code == 400, "una próxima acción sin fecha válida se rechaza")
    check(c.post("/api/accion", json={"fingerprint": fp, "texto": "Llamar", "fecha": "2026-10-20"}).status_code == 200, "guardar próxima acción")
    check(c.post("/api/evento", json={"fingerprint": fp, "tipo": "respuesta", "detalle": "Piden llamada"}).status_code == 200, "registrar una respuesta en la timeline")
    check(c.post("/api/ingreso", json={"fingerprint": fp, "monto_usd": "-5"}).status_code == 400, "ingreso negativo rechazado")
    check(c.post("/api/ingreso", json={"fingerprint": fp, "monto_usd": "250", "estado": "acordado"}).status_code == 200, "cargar un ingreso acordado")
    det = c.get(f"/ticket/{fp}").get_data(as_text=True)
    check("Piden llamada" in det and "Timeline" in det and "Por qué esta oportunidad" in det, "el detalle muestra timeline y desglose del score")
    check("USD 250" in c.get("/").get_data(as_text=True), "el ingreso suma en la barra de meta")
    r = c.post(f"/api/importaciones/{iid}/deshacer", json={})
    check(r.json["conservadas"] == 1 and r.json["borradas"] == 0, "deshacer no borra lo que ya postulaste")
    an = c.get("/analitica").get_data(as_text=True)
    check("Embudo" in an and "Skills del mercado" in an, "analítica con embudo y gap de skills")


def main() -> int:
    test_turso_adapter()
    test_fuentes()
    test_notify()
    test_fit_y_paralelo()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        test_store(Path(tmp) / "a.sqlite")
        test_web(Path(tmp) / "b.sqlite")
        test_crm(Path(tmp) / "c.sqlite")
        test_web_crm(Path(tmp) / "d.sqlite")
    print("\n✅ selftest_web OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
