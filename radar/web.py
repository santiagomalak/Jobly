"""CRM web de Jobly. Local: `python -m radar.main serve`. Producción: Vercel (app.py).

Seguridad: todo requiere login con JOBLY_PASSWORD; si no está configurada, la app no responde
(falla cerrada). Los POST de la API exigen JSON (un formulario de otro sitio no puede mandarlo)
y la cookie es SameSite=Lax. Las URLs externas se validan antes de ir a un href.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from datetime import timedelta
from pathlib import Path

from flask import Flask, Response, abort, g, jsonify, redirect, render_template, request, session, url_for

from . import ask as asistente
from . import db, fit
from . import icono as icono_mod
from . import seguimiento as seguimiento_mod
from .config import load_config
from .memory import Memory
from .models import Ticket
from .pitch import build_pitch
from .scoring import score_ticket
from .sources import parse_sheet_csv
from .store import ESTADOS, Store

MODULOS = ("AUTOMATION", "DATA", "WEB", "SCRAPING", "BOTS")
_FP = re.compile(r"^[0-9a-f]{32}$")
_MAX_IMPORT = 500


def _url_segura(url: str) -> str:
    return url if str(url).lower().startswith(("http://", "https://")) else "#"


_ETIQUETAS = {"tipo": "Tipo", "ubicacion": "Ubicación", "seniority": "Nivel", "salario": "Sueldo publicado"}
_TIPOS = {"full_time": "Full-time", "contract": "Contrato", "freelance": "Freelance", "part_time": "Part-time", "empleo": "Empleo"}


def _ticket_desde_datos(datos: dict) -> Ticket:
    datos = {k: v for k, v in datos.items() if k != "fingerprint"}
    return Ticket(**datos)


def _datos_oferta(tags: list[str]) -> list[tuple[str, str]]:
    """Etiquetas de las fuentes estructuradas -> pares legibles para mostrar en el detalle."""
    out = []
    for tag in tags:
        clave, _, valor = str(tag).partition(":")
        if clave in _ETIQUETAS and valor:
            out.append((_ETIQUETAS[clave], _TIPOS.get(valor, valor) if clave == "tipo" else valor))
    return out


def create_app(db_path: str | Path | None = None) -> Flask:
    cfg = load_config()
    root = Path(cfg["root"])
    password = os.environ.get("JOBLY_PASSWORD", "")

    app = Flask(__name__, template_folder="templates", static_folder=None)
    # La cookie de sesión se firma con una clave derivada de la contraseña. PBKDF2 (lento a
    # propósito) evita que alguien con una cookie pruebe contraseñas offline a alta velocidad.
    clave = os.environ.get("JOBLY_SECRET_KEY") or (
        hashlib.pbkdf2_hmac("sha256", password.encode(), b"jobly-session", 200_000).hex() if password else "sin-clave"
    )
    app.config.update(
        SECRET_KEY=clave,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=bool(os.environ.get("VERCEL")) or os.environ.get("JOBLY_SECURE_COOKIES") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        MAX_CONTENT_LENGTH=1_000_000,
        JSON_AS_ASCII=False,
    )
    app.jinja_env.filters["safe_url"] = _url_segura

    # ---------- acceso a datos ----------
    def store() -> Store:
        if "store" not in g:
            g.store = Store(db_path or root / cfg["db_path"])
        return g.store

    def memoria() -> Memory:
        return Memory(root / cfg["memory_dir"])

    @app.teardown_appcontext
    def _cerrar(_exc):
        s = g.pop("store", None)
        if s is not None:
            s.close()

    # ---------- guardia ----------
    @app.before_request
    def guardia():
        if request.endpoint in ("healthz", "manifest", "icono"):  # públicos: no contienen datos
            return None
        if not password:
            return "Falta configurar JOBLY_PASSWORD. La app no responde sin contraseña.", 503
        if os.environ.get("VERCEL") and not db.remoto_configurado():
            return "Falta configurar TURSO_DATABASE_URL y TURSO_AUTH_TOKEN (Vercel no guarda archivos).", 503
        if request.endpoint == "login":
            return None
        if not session.get("ok"):
            if request.path.startswith("/api/"):
                return jsonify(error="no autenticado"), 401
            return redirect(url_for("login"))
        if request.method == "POST" and request.path.startswith("/api/") and not request.is_json:
            return jsonify(error="se espera JSON"), 415
        return None

    @app.after_request
    def cabeceras(resp):
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    # ---------- páginas ----------
    @app.get("/healthz")
    def healthz():
        return jsonify(ok=True)

    @app.get("/manifest.webmanifest")
    def manifest():
        resp = jsonify(
            name="Jobly", short_name="Jobly", start_url="/", display="standalone", lang="es",
            background_color="#0b0d12", theme_color="#0b0d12",
            icons=[{"src": f"/icon-{n}.png", "sizes": f"{n}x{n}", "type": "image/png", "purpose": "any"} for n in (192, 512)],
        )
        resp.headers["Content-Type"] = "application/manifest+json"
        return resp

    @app.get("/icon-<int:lado>.png")
    def icono(lado: int):
        if lado not in (192, 512):
            abort(404)
        return Response(icono_mod.png(lado), mimetype="image/png", headers={"Cache-Control": "public, max-age=86400"})

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = ""
        if request.method == "POST":
            intento = (request.form.get("password") or "").encode()
            if hmac.compare_digest(intento, password.encode()):
                session.clear()
                session["ok"] = True
                session.permanent = True
                return redirect(url_for("index"))
            time.sleep(0.8)
            error = "Contraseña incorrecta"
        return render_template("login.html", error=error), (401 if error else 200)

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    def index():
        s = store()
        return render_template(
            "index.html",
            m=s.metricas(int(cfg.get("objetivo_semanal", 5)), int(cfg.get("meta_mensual_usd", 900))),
            pipeline=s.pipeline(),
            revisar=s.revisar(int(cfg.get("review_score", 30))),
            seguimientos=s.seguimientos_pendientes(),
            estados=ESTADOS,
        )

    @app.get("/ticket/<fp>")
    def ticket(fp: str):
        row = store().get(fp) if _FP.match(fp) else None
        if row is None:
            abort(404)
        try:
            datos = json.loads(row["payload"] or "{}")
        except ValueError:
            datos = {}
        debido = next((n for r, n, _ in store().seguimientos_pendientes() if r["fingerprint"] == fp), None)
        try:
            tk = _ticket_desde_datos(datos)
        except TypeError:  # payload dañado o vacío: se analiza con lo mínimo de la fila
            tk = Ticket(source=row["source"], title=row["title"], url=row["url"])
        return render_template(
            "ticket.html", t=row, d=datos, estados=ESTADOS,
            datos_oferta=_datos_oferta(datos.get("tags", [])), seguimiento_debido=debido,
            encaje=fit.analizar(tk, memoria()),
        )

    @app.get("/ask")
    def ask_page():
        oferta = ""
        fp = request.args.get("fp", "")
        if _FP.match(fp) and (row := store().get(fp)):
            try:
                d = json.loads(row["payload"] or "{}")
            except ValueError:
                d = {}
            oferta = f"{row['title']}\n{d.get('description', '')}"[:3000]
        return render_template("ask.html", oferta=oferta)

    @app.get("/analitica")
    def analitica_page():
        return render_template("analitica.html", a=store().analitica(), objetivo=int(cfg.get("objetivo_semanal", 5)))

    @app.get("/agregar")
    def agregar_page():
        return render_template("agregar.html", modulos=MODULOS)

    # ---------- API ----------
    def _fp_valido(datos: dict) -> str:
        fp = str(datos.get("fingerprint", ""))
        if not _FP.match(fp) or store().get(fp) is None:
            abort(404)
        return fp

    @app.post("/api/marcar")
    def api_marcar():
        datos = request.get_json(silent=True) or {}
        fp, estado = _fp_valido(datos), datos.get("estado")
        if estado not in ESTADOS:
            return jsonify(error="estado inválido"), 400
        store().marcar(fp, estado)
        return jsonify(ok=True, estado=estado)

    @app.post("/api/notas")
    def api_notas():
        datos = request.get_json(silent=True) or {}
        store().set_notas(_fp_valido(datos), str(datos.get("notas", "")))
        return jsonify(ok=True)

    def _ticket_desde_fila(row) -> Ticket:
        return _ticket_desde_datos(json.loads(row["payload"] or "{}"))

    @app.post("/api/pitch")
    def api_pitch():
        datos = request.get_json(silent=True) or {}
        fp = _fp_valido(datos)
        t = _ticket_desde_fila(store().get(fp))
        build_pitch(t, memoria())
        store().set_pitch(fp, t.pitch, t.pitch_engine)
        return jsonify(pitch=t.pitch, engine=t.pitch_engine)

    @app.post("/api/seguimiento")
    def api_seguimiento():
        datos = request.get_json(silent=True) or {}
        fp = _fp_valido(datos)
        fila = store().get(fp)
        numero = int(fila["seguimientos"] or 0) + 1
        if numero > 2:
            return jsonify(error="Ya mandaste los 2 seguimientos. Después, silencio."), 400
        texto, motor = seguimiento_mod.redactar(_ticket_desde_fila(fila), numero, memoria())
        return jsonify(text=texto, engine=motor, numero=numero)

    @app.post("/api/seguimiento_hecho")
    def api_seguimiento_hecho():
        datos = request.get_json(silent=True) or {}
        return jsonify(ok=True, seguimientos=store().registrar_seguimiento(_fp_valido(datos)))

    @app.post("/api/ask")
    def api_ask():
        datos = request.get_json(silent=True) or {}
        pregunta = str(datos.get("pregunta", "")).strip()
        if not pregunta:
            return jsonify(error="Escribí la pregunta"), 400
        try:
            tope = int(datos["max_chars"]) if datos.get("max_chars") else None
        except (TypeError, ValueError):
            return jsonify(error="El tope de caracteres debe ser un número"), 400
        if tope is not None and not 20 <= tope <= 5000:
            return jsonify(error="El tope debe estar entre 20 y 5000"), 400
        res = asistente.answer(pregunta, memoria(), max_chars=tope, oferta=str(datos.get("oferta", "")))
        return jsonify(
            text=res.text, engine=res.engine, chars=res.chars, truncated=res.truncated, missing=res.missing
        )

    @app.post("/api/ticket")
    def api_ticket():
        """Carga manual: pegás una oferta que encontraste vos (Workana, LinkedIn, lo que sea)."""
        datos = request.get_json(silent=True) or {}
        url = str(datos.get("url", "")).strip()
        desc = str(datos.get("description", "")).strip()
        if not url.lower().startswith(("http://", "https://")):
            return jsonify(error="La URL debe empezar con http:// o https://"), 400
        if len(desc) < 30:
            return jsonify(error="Pegá la descripción de la oferta (mínimo 30 caracteres)"), 400
        modulo = str(datos.get("modulo", "auto")).upper()
        t = Ticket(
            source="manual",
            title=str(datos.get("title", "")).strip()[:160] or desc[:90],
            url=url,
            description=desc[:4000],
            raw_budget=str(datos.get("budget", "")).strip()[:60],
        )
        previo = store().get_by_url(url)  # el fingerprint incluye el título: la misma URL con otro título no es nueva
        if previo:
            return jsonify(ok=True, fingerprint=previo["fingerprint"], existente=True)
        mem = memoria()
        score_ticket(t, mem.taxonomia(), cfg)
        if modulo in MODULOS:
            t.module = modulo
        if not t.module:
            return jsonify(error="No detecté el tipo de trabajo: elegí un módulo", necesita_modulo=True), 422
        t.verdict = "pass"  # la cargaste vos: entra al pipeline aunque el scoring dude
        build_pitch(t, mem)
        store().save(t)
        return jsonify(ok=True, fingerprint=t.fingerprint, score=t.score, module=t.module)

    @app.post("/api/importar")
    def api_importar():
        """Pega filas de Excel/Sheets: se puntúan como cualquier otro ticket (sin pitch)."""
        datos = request.get_json(silent=True) or {}
        try:
            tickets = parse_sheet_csv(str(datos.get("csv", "")), "importado")
        except RuntimeError as exc:
            return jsonify(error=str(exc)), 400
        if len(tickets) > _MAX_IMPORT:
            return jsonify(error=f"Máximo {_MAX_IMPORT} filas por importación"), 400
        s, mem = store(), memoria()
        tax, conocidos = mem.taxonomia(), s.known_set()
        nuevos = []
        for t in tickets:
            if t.fingerprint in conocidos or not t.url.lower().startswith(("http://", "https://")):
                continue
            conocidos.add(t.fingerprint)
            score_ticket(t, tax, cfg)
            nuevos.append((t, False))
        s.save_many(nuevos)
        return jsonify(
            ok=True,
            filas=len(tickets),
            nuevos=len(nuevos),
            aprobados=sum(1 for t, _ in nuevos if t.verdict == "pass"),
        )

    return app
