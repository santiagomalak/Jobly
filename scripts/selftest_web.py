"""Prueba la app web y la capa Turso sin internet ni claves reales.

  python scripts/selftest_web.py
"""
from __future__ import annotations

import os
import sys
import tempfile
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
    s.close()


def test_web(path: Path) -> None:
    print("Web")
    os.environ["JOBLY_PASSWORD"] = "clave-de-prueba"
    app = create_app(db_path=path)
    c = app.test_client()

    r = c.get("/healthz")
    check(r.status_code == 200, "/healthz responde sin login")
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
        check(c.get("/ticket/../../etc/passwd").status_code == 404, "fingerprint inválido da 404")

        r = c.post("/api/marcar", json={"fingerprint": fp, "estado": "postulado"})
        check(r.status_code == 200, "marcar como postulado")
        check(c.post("/api/marcar", json={"fingerprint": fp, "estado": "hackeado"}).status_code == 400, "estado inválido rechazado")
        check(c.post("/api/notas", json={"fingerprint": fp, "notas": "hola"}).status_code == 200, "guardar notas")
        r = c.post("/api/pitch", json={"fingerprint": fp})
        check(r.status_code == 200 and r.json["engine"] == "test", "regenerar pitch")

        r = c.post("/api/ask", json={"pregunta": "¿Qué frameworks usás?", "max_chars": 300})
        check(r.status_code == 200 and r.json["text"], "el asistente responde")
        check(c.post("/api/ask", json={"pregunta": "  "}).status_code == 400, "pregunta vacía rechazada")
        check(c.post("/api/ask", json={"pregunta": "x", "max_chars": 9}).status_code == 400, "tope fuera de rango rechazado")

    csv_texto = "url\ttitle\tdescription\nhttps://e.com/a\tScraper\tweb scraping con playwright, presupuesto $200\nnotaurl\tX\ty\n"
    r = c.post("/api/importar", json={"csv": csv_texto})
    check(r.status_code == 200 and r.json["nuevos"] == 1, "importa filas pegadas (TSV) y descarta URLs inválidas")
    check(c.post("/api/importar", json={"csv": "titulo,descripcion\na,b"}).status_code == 400, "CSV sin columna url rechazado")

    Store(path).save(Ticket(source="x", title="Malicioso", url="javascript:alert(1)", description="d",
                            module="WEB", score=60, verdict="pass"))
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
    with tempfile.TemporaryDirectory() as tmp:
        test_store(Path(tmp) / "a.sqlite")
        test_web(Path(tmp) / "b.sqlite")
    print("\n✅ selftest_web OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
