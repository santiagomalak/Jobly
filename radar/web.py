"""CRM web de Jobly. Local: `python -m radar.main serve`. Producción: Vercel (app.py).

Seguridad: todo requiere login con JOBLY_PASSWORD; si no está configurada, la app no responde
(falla cerrada). Los POST de la API exigen JSON (un formulario de otro sitio no puede mandarlo)
y la cookie es SameSite=Lax. Las URLs externas se validan antes de ir a un href.
"""
from __future__ import annotations

import csv
import dataclasses
import hashlib
import hmac
import io
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, Response, abort, g, jsonify, redirect, render_template, request, session, url_for

from . import ask as asistente
from . import copiloto, db, fit, importador
from . import plantillas as plantillas_mod
from . import etapas as et
from . import normalizar as norm
from . import icono as icono_mod
from . import seguimiento as seguimiento_mod
from .config import load_config
from .memory import Memory
from .models import Ticket
from .pitch import build_pitch
from .oportunidad import calcular
from .scoring import score_ticket
from .sources import parse_sheet_csv
from .store import ESTADOS, Store, etapa_de

MODULOS = ("AUTOMATION", "DATA", "WEB", "SCRAPING", "BOTS")
_FP = re.compile(r"^[0-9a-f]{32}$")
_MAX_IMPORT = 500
_MAX_POSTULACIONES = 100  # cada fila son ~3 viajes a la base: 100 entran holgadas en 60 s
_LOGIN_MAX_FALLOS = 10
_LOGIN_VENTANA_MIN = 15
_CAMPOS_TICKET = {f.name for f in dataclasses.fields(Ticket)}


def _url_segura(url: str) -> str:
    return url if str(url).lower().startswith(("http://", "https://")) else "#"


_ETIQUETAS = {"tipo": "Tipo", "ubicacion": "Ubicación", "seniority": "Nivel", "salario": "Sueldo publicado"}
_TIPOS = {"full_time": "Full-time", "contract": "Contrato", "freelance": "Freelance", "part_time": "Part-time", "empleo": "Empleo"}


def _ticket_desde_datos(datos: dict) -> Ticket:
    """Payload JSON -> Ticket, ignorando claves que el modelo ya no (o todavía no) tiene."""
    return Ticket(**{k: v for k, v in datos.items() if k in _CAMPOS_TICKET})


def _ip() -> str:
    """IP del cliente. En Vercel la pone el proxy en x-real-ip / x-forwarded-for."""
    reenviada = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for", "").split(",")[0]
    return (reenviada or request.remote_addr or "?").strip()[:64]


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _datos_oferta(tags: list[str]) -> list[tuple[str, str]]:
    """Etiquetas de las fuentes estructuradas -> pares legibles para mostrar en el detalle."""
    out = []
    for tag in tags:
        clave, _, valor = str(tag).partition(":")
        if clave in _ETIQUETAS and valor:
            out.append((_ETIQUETAS[clave], _TIPOS.get(valor, valor) if clave == "tipo" else valor))
    return out


_ETIQUETAS_EXTRA = {
    "empresa": "Empresa / cliente", "modalidad": "Modalidad", "duracion_dias": "Duración (días)",
    "cliente_verificado": "Cliente verificado", "proyectos_previos_cliente": "Proyectos previos del cliente",
    "calificacion_cliente": "Calificación del cliente", "gasto_total_cliente_usd": "Gasto total del cliente (USD)",
    "propuestas_recibidas": "Propuestas recibidas", "idioma": "Idioma", "contacto": "Contacto",
}


def _datos_extra(extra: dict) -> list[tuple[str, str]]:
    out = []
    for clave, etiqueta in _ETIQUETAS_EXTRA.items():
        valor = extra.get(clave)
        if valor in (None, ""):
            continue
        if clave == "cliente_verificado":
            valor = "sí" if valor == 1 else "no"
        out.append((etiqueta, str(valor)))
    if extra.get("presupuesto_min") or extra.get("presupuesto_max"):
        rango = "–".join(str(v) for v in dict.fromkeys([extra.get("presupuesto_min"), extra.get("presupuesto_max")]) if v)
        periodo = {"hora": "/h", "mes": "/mes", "proyecto": " por proyecto"}.get(extra.get("periodo_pago") or "", "")
        out.append(("Presupuesto", f"{extra.get('moneda') or 'USD'} {rango}{periodo}"))
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

    def completar_oportunidad(filas: list) -> None:
        """Calcula y guarda el score de oportunidad de filas que todavía no lo tienen."""
        perfil = fit.texto_perfil(memoria())
        cambios = []
        for fp, datos in store().payloads([r["fingerprint"] for r in filas[:200]]).items():
            try:
                tk = _ticket_desde_datos(datos)
            except TypeError:
                continue
            puntos, detalle = calcular(tk, perfil, cfg)
            cambios.append((puntos, detalle, fp))
        store().set_oportunidad(cambios)

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
            ip, ahora = _ip(), datetime.now(timezone.utc).replace(tzinfo=None)
            limite = _ts(ahora - timedelta(minutes=_LOGIN_VENTANA_MIN))
            conn = store().conn
            fila = conn.execute("SELECT fallos, desde FROM login_intentos WHERE ip = ?", (ip,)).fetchone()
            if fila and fila["fallos"] >= _LOGIN_MAX_FALLOS and fila["desde"] >= limite:
                return render_template(
                    "login.html", error=f"Demasiados intentos. Probá de nuevo en {_LOGIN_VENTANA_MIN} minutos."
                ), 429
            intento = (request.form.get("password") or "").encode()
            if hmac.compare_digest(intento, password.encode()):
                conn.execute("DELETE FROM login_intentos WHERE ip = ?", (ip,))
                session.clear()
                session["ok"] = True
                session.permanent = True
                return redirect(url_for("index"))
            conn.execute(
                """INSERT INTO login_intentos (ip, fallos, desde) VALUES (?, 1, ?)
                   ON CONFLICT(ip) DO UPDATE SET
                     fallos = CASE WHEN login_intentos.desde < ? THEN 1 ELSE login_intentos.fallos + 1 END,
                     desde = CASE WHEN login_intentos.desde < ? THEN excluded.desde ELSE login_intentos.desde END""",
                (ip, _ts(ahora), limite, limite),
            )
            time.sleep(0.8)
            error = "Contraseña incorrecta"
        return render_template("login.html", error=error), (401 if error else 200)

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    def index():
        t = store().tablero(cfg, completar=completar_oportunidad)
        return render_template(
            "index.html", t=t, m=t["metricas"], meta=copiloto.meta(t, cfg), hoy=copiloto.hoy(t),
            seguimientos=t["seguimientos"], revisar=t["revisar"], etiquetas=et.ETIQUETAS, etapa_de=etapa_de,
        )

    @app.get("/ticket/<fp>")
    def ticket(fp: str):
        if not _FP.match(fp):
            abort(404)
        det = store().detalle(fp)
        row = det["row"]
        if row is None:
            abort(404)
        try:
            datos = json.loads(row["payload"] or "{}")
        except ValueError:
            datos = {}
        ahora = datetime.now(timezone.utc).replace(tzinfo=None)
        debido = next((n for _, n, _ in store()._vencidos([row], ahora)), None)
        try:
            tk = _ticket_desde_datos(datos)
        except TypeError:  # payload dañado o vacío: se analiza con lo mínimo de la fila
            tk = Ticket(source=row["source"], title=row["title"], url=row["url"])
        try:
            detalle_score = json.loads(row["score_detalle"] or "[]")
        except ValueError:
            detalle_score = []
        if row["score_oportunidad"] is None:
            puntos, detalle_score = calcular(tk, fit.texto_perfil(memoria()), cfg)
            store().set_oportunidad([(puntos, detalle_score, fp)])
            row = store().get(fp)
        return render_template(
            "ticket.html", t=row, d=datos, etapa=etapa_de(row), etapas=et.ETAPAS, etiquetas=et.ETIQUETAS,
            datos_oferta=_datos_oferta(datos.get("tags", [])) + _datos_extra(tk.extra), seguimiento_debido=debido,
            encaje=fit.analizar(tk, memoria()), detalle_score=detalle_score,
            plantillas=plantillas_mod.listar(store().conn, "empleo" if row["tipo"] == "empleo" else "freelance"),
            plantillas_seg=plantillas_mod.listar(store().conn, "seguimiento") if debido else [],
            eventos=det["eventos"], ingresos=det["ingresos"], hoy=(ahora - timedelta(hours=3)).date().isoformat(),
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
        return render_template(
            "analitica.html", a=store().analitica(), objetivo=int(cfg.get("objetivo_semanal", 5)), gap=_gap(),
        )

    def _gap(dias: int = 30, limite: int = 400) -> dict:
        """Tecnologías más pedidas en lo relevado (últimos `dias`) contra lo que dice tu perfil."""
        rows = store().conn.execute(
            """SELECT title, substr(payload, 1, 3000) AS p FROM tickets
               WHERE seen_at >= datetime('now', ?) ORDER BY seen_at DESC LIMIT ?""",
            (f"-{dias} days", limite),
        ).fetchall()
        perfil = fit.texto_perfil(memoria())
        cuentas: dict[str, int] = {}
        tenes: set[str] = set()
        for r in rows:
            enc = fit.encaje_texto(f"{r['title']} {r['p']}".lower(), perfil)
            tenes.update(enc.tenes)
            for tec in enc.tenes + enc.faltan:
                cuentas[tec] = cuentas.get(tec, 0) + 1
        orden = sorted(cuentas.items(), key=lambda x: -x[1])
        return {
            "avisos": len(rows),
            "faltan": [(k, n) for k, n in orden if k not in tenes][:12],
            "tenes": [(k, n) for k, n in orden if k in tenes][:12],
        }

    @app.get("/importar")
    def importar_page():
        return render_template(
            "importar.html", campos=importador.CAMPOS, historial=importador.historial(store().conn),
            max_filas=importador.MAX_FILAS, max_chunk=importador.MAX_CHUNK,
        )

    @app.get("/exportar.csv")
    def exportar():
        """Tu pipeline en CSV (backup / análisis en planilla). Celdas neutralizadas contra fórmulas."""
        cols = ("fingerprint", "title", "url", "source", "tipo", "etapa", "score", "score_oportunidad",
                "budget_usd", "presupuesto_min", "presupuesto_max", "moneda", "periodo_pago", "seen_at",
                "postulado_at", "estado_at", "seguimientos", "proxima_accion", "proxima_accion_at", "notas")
        rows = store().conn.execute(
            f"""SELECT {', '.join(cols)}, estado FROM tickets
                WHERE verdict = 'pass' OR postulado_at IS NOT NULL OR COALESCE(etapa, 'relevada') != 'relevada'
                ORDER BY seen_at DESC"""
        ).fetchall()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        for r in rows:
            w.writerow([norm.celda_export(etapa_de(r) if c == "etapa" else r[c]) for c in cols])
        return Response(
            "\ufeff" + buf.getvalue(), mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=jobly-pipeline.csv"},
        )

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

    @app.post("/api/costo")
    def api_costo():
        datos = request.get_json(silent=True) or {}
        try:
            costo = int(datos.get("costo_usd", 0))
        except (TypeError, ValueError):
            return jsonify(error="costo inválido"), 400
        store().set_costo(_fp_valido(datos), costo)
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
        plantillas_mod.asignar(store().conn, fp, None)  # el pitch ya no sale de una plantilla
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

    @app.post("/api/postulaciones/importar")
    def api_postulaciones_importar():
        """Pega un CSV de postulaciones que YA mandaste (vos, a mano, en cualquier plataforma):
        url (obligatoria), title, description (se guarda como nota de la postulación), budget.
        Si la url ya está en el pipeline, la marca 'postulado'; si no existe, la crea y la marca
        de una. Es constancia, no scoring: no hace falta que pase ningún filtro."""
        datos = request.get_json(silent=True) or {}
        try:
            filas = parse_sheet_csv(str(datos.get("csv", "")), "manual-postulado")
        except RuntimeError as exc:
            return jsonify(error=str(exc)), 400
        if len(filas) > _MAX_POSTULACIONES:
            return jsonify(error=f"Máximo {_MAX_POSTULACIONES} filas por vez (partilo en tandas)"), 400
        s, mem, tax = store(), memoria(), memoria().taxonomia()
        emparejados, creados = 0, 0
        for t in filas:
            if not t.url.lower().startswith(("http://", "https://")):
                continue
            previo = s.get_by_url(t.url)
            if previo:
                s.marcar(previo["fingerprint"], "postulado")
                if t.description:
                    s.set_notas(previo["fingerprint"], t.description)
                emparejados += 1
                continue
            score_ticket(t, tax, cfg)
            t.verdict = "pass"
            s.save(t)
            s.marcar(t.fingerprint, "postulado")
            if t.description:
                s.set_notas(t.fingerprint, t.description)
            creados += 1
        return jsonify(ok=True, filas=len(filas), emparejados=emparejados, creados=creados)

    @app.post("/api/etapa")
    def api_etapa():
        datos = request.get_json(silent=True) or {}
        fp, etapa = _fp_valido(datos), datos.get("etapa")
        if etapa not in et.ETAPAS:
            return jsonify(error="etapa inválida"), 400
        store().mover(fp, etapa, str(datos.get("detalle", "")))
        row = store().get(fp)
        return jsonify(ok=True, etapa=etapa, proxima_accion=row["proxima_accion"],
                       proxima_accion_at=row["proxima_accion_at"])

    @app.post("/api/accion")
    def api_accion():
        datos = request.get_json(silent=True) or {}
        fp = _fp_valido(datos)
        fecha = norm.fecha_iso(datos.get("fecha"))
        texto = str(datos.get("texto", ""))
        if texto.strip() and not fecha:
            return jsonify(error="Elegí una fecha para la próxima acción"), 400
        # La fecha del formulario es un día de Argentina: se guarda a las 09:00 ART (12:00 UTC).
        store().set_proxima_accion(fp, texto, f"{fecha} 12:00:00" if fecha else None)
        return jsonify(ok=True)

    @app.post("/api/evento")
    def api_evento():
        datos = request.get_json(silent=True) or {}
        fp, tipo = _fp_valido(datos), datos.get("tipo")
        detalle = str(datos.get("detalle", "")).strip()
        if tipo not in ("envio", "respuesta", "entrevista", "nota") or not detalle:
            return jsonify(error="Elegí el tipo y escribí el detalle"), 400
        store().agregar_evento(fp, tipo, detalle)
        return jsonify(ok=True)

    @app.post("/api/ingreso")
    def api_ingreso():
        datos = request.get_json(silent=True) or {}
        fp = _fp_valido(datos) if datos.get("fingerprint") else None
        try:
            monto = int(float(datos.get("monto_usd")))
        except (TypeError, ValueError):
            return jsonify(error="Monto inválido"), 400
        estado = datos.get("estado", "acordado")
        hoy = (datetime.now(timezone.utc) - timedelta(hours=3)).date().isoformat()
        fecha = norm.fecha_iso(datos.get("fecha")) or hoy
        if monto <= 0 or estado not in ("acordado", "cobrado"):
            return jsonify(error="El monto tiene que ser mayor a 0 y el estado acordado o cobrado"), 400
        store().agregar_ingreso(fp, monto, estado, fecha, str(datos.get("detalle", "")))
        return jsonify(ok=True)

    @app.post("/api/ingreso/<int:ingreso_id>/<accion>")
    def api_ingreso_accion(ingreso_id: int, accion: str):
        if accion == "cobrado":
            store().marcar_cobrado(ingreso_id)
        elif accion == "borrar":
            store().borrar_ingreso(ingreso_id)
        else:
            abort(404)
        return jsonify(ok=True)

    # ---------- importador ----------
    def _importacion() -> importador.Importacion:
        mem = memoria()
        return importador.Importacion(store(), cfg, mem.taxonomia(), fit.texto_perfil(mem))

    @app.get("/api/mapeo")
    def api_mapeo():
        return jsonify(mapeo=importador.mapeo_guardado(store().conn, request.args.get("fuente", "")[:40]))

    @app.post("/api/importaciones")
    def api_importacion_crear():
        datos = request.get_json(silent=True) or {}
        mapeo = datos.get("mapeo") if isinstance(datos.get("mapeo"), dict) else None
        if mapeo:
            mapeo = {str(k)[:80]: str(v) for k, v in list(mapeo.items())[:60] if v in importador.CAMPOS}
        iid = _importacion().crear(
            str(datos.get("fuente", "")).strip().lower(), str(datos.get("politica", "ignorar")), mapeo
        )
        return jsonify(ok=True, id=iid)

    @app.post("/api/importaciones/<int:iid>/chunk")
    def api_importacion_chunk(iid: int):
        datos = request.get_json(silent=True) or {}
        filas = datos.get("filas")
        if not isinstance(filas, list) or not filas or len(filas) > importador.MAX_CHUNK:
            return jsonify(error=f"Mandá entre 1 y {importador.MAX_CHUNK} filas por envío"), 400
        try:
            desde = max(0, int(datos.get("desde", 0)))
            return jsonify(ok=True, **_importacion().chunk(iid, filas, desde))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    @app.post("/api/importaciones/<int:iid>/deshacer")
    def api_importacion_deshacer(iid: int):
        try:
            return jsonify(ok=True, **_importacion().deshacer(iid))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    # ---------- biblioteca de propuestas ----------
    @app.get("/plantillas")
    def plantillas_page():
        conn = store().conn
        return render_template(
            "plantillas.html", plantillas=plantillas_mod.listar(conn), base=plantillas_mod.sin_plantilla(conn),
            tipos=plantillas_mod.TIPOS, idiomas=plantillas_mod.IDIOMAS, variables=plantillas_mod.VARIABLES,
        )

    @app.post("/api/plantillas")
    def api_plantilla_guardar():
        datos = request.get_json(silent=True) or {}
        try:
            pid = int(datos.get("id") or 0) or None
            pid = plantillas_mod.guardar(
                store().conn, str(datos.get("nombre", "")), str(datos.get("tipo", "freelance")),
                str(datos.get("idioma", "es")), str(datos.get("cuerpo", "")), pid,
            )
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        return jsonify(ok=True, id=pid)

    @app.post("/api/plantillas/<int:pid>/borrar")
    def api_plantilla_borrar(pid: int):
        plantillas_mod.borrar(store().conn, pid)
        return jsonify(ok=True)

    @app.post("/api/plantillas/base")
    def api_plantillas_base():
        return jsonify(ok=True, cargadas=plantillas_mod.cargar_base(store().conn, root / cfg["memory_dir"]))

    @app.post("/api/plantilla/usar")
    def api_plantilla_usar():
        """Rellena la plantilla con los datos del ticket. Si es una propuesta, queda como pitch
        y se anota qué plantilla se usó para medir su tasa de respuesta."""
        datos = request.get_json(silent=True) or {}
        fp = _fp_valido(datos)
        try:
            p = plantillas_mod.obtener(store().conn, int(datos.get("id") or 0))
        except (TypeError, ValueError):
            p = None
        fila = store().get(fp)
        if p is None or fila is None:
            return jsonify(error="Plantilla o ticket inexistente"), 404
        texto = plantillas_mod.rellenar(p["cuerpo"], plantillas_mod.valores(fila))
        if p["tipo"] != "seguimiento":
            store().set_pitch(fp, texto, "biblioteca")
            plantillas_mod.asignar(store().conn, fp, p["id"])
        return jsonify(ok=True, texto=texto, pendientes=plantillas_mod.pendientes(texto), nombre=p["nombre"])

    return app
