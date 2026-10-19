"""Importador de vacantes en CSV (el formato estándar del prompt de Claude in Chrome o cualquier
planilla mapeada a mano).

El navegador parsea el archivo y lo manda en chunks de hasta 100 filas ya mapeadas a los campos
de abajo: cada chunk es un request corto (muy lejos de los 60 s de Vercel) y se escribe en una
sola transacción. Una fila inválida se reporta y no frena el lote. Cada ticket creado guarda el
`import_id`, y los actualizados dejan un snapshot: así un lote entero se puede deshacer.
"""
from __future__ import annotations

import json
from typing import Any

from . import db
from . import normalizar as norm
from .models import Ticket
from .oportunidad import calcular
from .scoring import score_ticket

CAMPOS = (
    "titulo", "empresa_o_cliente", "url", "fuente", "tipo", "modalidad", "pais", "seniority",
    "presupuesto_min", "presupuesto_max", "moneda", "periodo_pago", "duracion_estimada", "stack",
    "requisitos", "idioma", "cliente_verificado", "proyectos_previos_cliente", "calificacion_cliente",
    "gasto_total_cliente_usd", "propuestas_recibidas", "fecha_publicacion", "fecha_relevamiento",
    "contacto", "notas", "descripcion",
)
MAX_CHUNK = 100

# Columnas que "actualizar" pisa y que "deshacer" restaura.
_SNAP = ("payload", "score", "verdict", "module", "budget_usd", "tipo", "score_oportunidad", "score_detalle",
         "presupuesto_min", "presupuesto_max", "moneda", "periodo_pago", "duracion_dias", "idioma",
         "propuestas_recibidas", "empresa_id")
MAX_FILAS = 2000

_TIPOS = {
    "empleo": "empleo", "job": "empleo", "full time": "empleo", "full-time": "empleo", "fulltime": "empleo",
    "part time": "empleo", "part-time": "empleo", "puesto": "empleo", "relacion de dependencia": "empleo",
    "freelance": "freelance", "proyecto": "freelance", "project": "freelance", "contract": "freelance",
    "contrato": "freelance", "gig": "freelance", "por proyecto": "freelance",
}
_PERIODOS = {"hora": "hora", "hour": "hora", "hr": "hora", "hourly": "hora", "h": "hora",
             "mes": "mes", "month": "mes", "monthly": "mes", "mensual": "mes",
             "proyecto": "proyecto", "project": "proyecto", "fixed": "proyecto", "fijo": "proyecto"}
_MODALIDADES = {"remoto": "remoto", "remote": "remoto", "hibrido": "hibrido", "hybrid": "hibrido",
                "presencial": "presencial", "on site": "presencial", "onsite": "presencial"}


def validar(fila: dict[str, Any], fuente_lote: str) -> tuple[Ticket | None, str]:
    """Fila mapeada -> (Ticket, '') o (None, motivo del error)."""
    f = {k: norm.celda(fila.get(k, "")) for k in CAMPOS}
    url = f["url"]
    if not url.lower().startswith(("http://", "https://")):
        return None, "url vacía o que no empieza con http(s)://"
    titulo = f["titulo"][:200]
    if not titulo:
        return None, "falta el título"
    tipo_crudo = norm.slug(f["tipo"])
    tipo = _TIPOS.get(tipo_crudo, "")
    if tipo_crudo and not tipo:
        return None, f"tipo desconocido: '{f['tipo'][:30]}' (usá empleo o freelance)"
    pmin, pmax = norm.entero(f["presupuesto_min"]), norm.entero(f["presupuesto_max"])
    if pmin is not None and pmax is not None and pmin > pmax:
        pmin, pmax = pmax, pmin
    calif = norm.decimal(f["calificacion_cliente"])
    if calif is not None and not 0 <= calif <= 5:
        calif = None
    periodo = _PERIODOS.get(norm.slug(f["periodo_pago"]), "")
    moneda = f["moneda"].upper().replace("US$", "USD").replace("$", "USD")[:5] if f["moneda"] else ("USD" if pmin or pmax else "")

    extra: dict[str, Any] = {
        "tipo": tipo,
        "empresa": f["empresa_o_cliente"][:120],
        "modalidad": _MODALIDADES.get(norm.slug(f["modalidad"]), f["modalidad"][:20].lower()),
        "pais": f["pais"][:80],
        "seniority": f["seniority"][:30].lower(),
        "presupuesto_min": pmin,
        "presupuesto_max": pmax,
        "moneda": moneda,
        "periodo_pago": periodo,
        "duracion_dias": norm.decimal(f["duracion_estimada"]),
        "stack": f["stack"][:500],
        "requisitos": f["requisitos"][:1000],
        "idioma": norm.slug(f["idioma"])[:2] if norm.slug(f["idioma"])[:2] in ("es", "pt", "en") else "",
        "cliente_verificado": norm.si_no(f["cliente_verificado"]),
        "proyectos_previos_cliente": norm.entero(f["proyectos_previos_cliente"]),
        "calificacion_cliente": calif,
        "gasto_total_cliente_usd": norm.entero(f["gasto_total_cliente_usd"]),
        "propuestas_recibidas": norm.entero(f["propuestas_recibidas"]),
        "fecha_relevamiento": norm.fecha_iso(f["fecha_relevamiento"]),
        "contacto": f["contacto"][:200],
        "notas": f["notas"][:500],
    }
    partes = [f["descripcion"], f["requisitos"] and f"Requisitos: {f['requisitos']}",
              f["stack"] and f"Stack: {f['stack'].replace('|', ',')}", f["notas"] and f"Notas: {f['notas']}"]
    tags = []
    if tipo == "empleo":
        tags.append("tipo:empleo")
    if extra["pais"]:
        tags.append(f"ubicacion:{extra['pais']}")
    if extra["seniority"]:
        tags.append(f"seniority:{extra['seniority']}")
    presupuesto = ""
    if pmin or pmax:
        presupuesto = f"{moneda} {pmin or pmax}" + (f"-{pmax}" if pmin and pmax and pmax != pmin else "") + (f" por {periodo}" if periodo else "")
    t = Ticket(
        source=(f["fuente"] or fuente_lote or "importado").lower()[:40],
        title=titulo,
        url=url,
        description="\n\n".join(p for p in partes if p)[:4000],
        published=norm.fecha_iso(f["fecha_publicacion"]),
        raw_budget=presupuesto,
        tags=tags,
        extra=extra,
    )
    return t, ""


class Importacion:
    def __init__(self, store: Any, cfg: dict[str, Any], taxonomia: dict[str, Any], perfil: str):
        self.store, self.conn, self.cfg, self.tax, self.perfil = store, store.conn, cfg, taxonomia, perfil

    def crear(self, fuente: str, politica: str, mapeo: dict[str, str] | None) -> int:
        politica = politica if politica in ("ignorar", "actualizar") else "ignorar"
        pasos = [("INSERT INTO importaciones (fuente, politica) VALUES (?, ?)", (fuente[:40] or "importado", politica))]
        if mapeo:
            pasos.append((
                """INSERT INTO mapeos_csv (fuente, mapeo, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(fuente) DO UPDATE SET mapeo = excluded.mapeo, updated_at = excluded.updated_at""",
                (fuente[:40] or "importado", json.dumps(mapeo, ensure_ascii=False)[:5000]),
            ))
        db.transaccion(self.conn, pasos)
        row = self.conn.execute("SELECT MAX(id) AS id FROM importaciones").fetchone()
        return int(row["id"])

    def chunk(self, import_id: int, filas: list[dict[str, Any]], desde: int = 0) -> dict[str, Any]:
        imp = self.conn.execute("SELECT * FROM importaciones WHERE id = ?", (import_id,)).fetchone()
        if imp is None or imp["deshecha_at"]:
            raise ValueError("importación inexistente o deshecha")
        filas = filas[:MAX_CHUNK]
        errores: list[dict[str, Any]] = []
        validas: list[tuple[int, Ticket]] = []
        for i, fila in enumerate(filas):
            t, error = validar(fila if isinstance(fila, dict) else {}, imp["fuente"])
            if t is None:
                errores.append({"fila": desde + i + 1, "motivo": error})
            else:
                validas.append((desde + i + 1, t))

        # Dedupe contra la base (un viaje) y dentro del mismo chunk
        urls = sorted({norm.url_norm(t.url) for _, t in validas})
        claves = sorted({c for _, t in validas if (c := norm.clave(t.extra.get("empresa"), t.title))})
        existentes: dict[str, Any] = {}
        if urls or claves:
            cond, args = [], []
            if urls:
                cond.append(f"url_norm IN ({','.join('?' * len(urls))})")
                args += urls
            if claves:
                cond.append(f"clave_norm IN ({','.join('?' * len(claves))})")
                args += claves
            for r in self.conn.execute(
                f"SELECT fingerprint, url_norm, clave_norm, {', '.join(_SNAP)} FROM tickets WHERE {' OR '.join(cond)}",
                tuple(args),
            ).fetchall():
                existentes[r["url_norm"]] = r
                if r["clave_norm"]:
                    existentes[r["clave_norm"]] = r

        empresas = self._empresas([t for _, t in validas])
        pasos: list[tuple[str, tuple]] = []
        snapshot: list[dict[str, Any]] = []
        vistos: set[str] = set()
        creadas = actualizadas = ignoradas = 0
        from .store import _UPSERT, _fila  # import diferido (store importa este paquete)

        for n, t in validas:
            u, c = norm.url_norm(t.url), norm.clave(t.extra.get("empresa"), t.title)
            if u in vistos or (c and c in vistos):
                ignoradas += 1
                continue
            vistos.update(x for x in (u, c) if x)
            previo = existentes.get(u) or (existentes.get(c) if c else None)
            self._puntuar(t)
            emp_id = empresas.get(norm.slug(t.extra.get("empresa")))
            if previo is None:
                pasos.append((_UPSERT, _fila(t, False, import_id=import_id, empresa_id=emp_id)))
                creadas += 1
            elif imp["politica"] == "actualizar":
                snapshot.append({k: previo[k] for k in ("fingerprint",) + _SNAP})
                t_fp = previo["fingerprint"]
                fila = list(_fila(t, False, import_id=None, empresa_id=emp_id))
                pasos.append((
                    """UPDATE tickets SET payload = ?, score = ?, verdict = ?, module = ?, budget_usd = ?, tipo = ?,
                         score_oportunidad = ?, score_detalle = ?, presupuesto_min = ?, presupuesto_max = ?, moneda = ?,
                         periodo_pago = ?, duracion_dias = ?, idioma = ?, propuestas_recibidas = ?,
                         empresa_id = COALESCE(?, empresa_id), clave_norm = COALESCE(clave_norm, ?)
                       WHERE fingerprint = ?""",
                    (fila[10], fila[5], fila[7], fila[4], fila[6], fila[12], fila[15], fila[16], fila[17], fila[18],
                     fila[19], fila[20], fila[21], fila[22], fila[23], emp_id, fila[14], t_fp),
                ))
                actualizadas += 1
            else:
                ignoradas += 1

        pasos.append((
            """UPDATE importaciones SET filas = filas + ?, creadas = creadas + ?, actualizadas = actualizadas + ?,
                 ignoradas = ignoradas + ?, con_error = con_error + ?,
                 errores = json(?), snapshot = json(?) WHERE id = ?""",
            (len(filas), creadas, actualizadas, ignoradas, len(errores),
             json.dumps((json.loads(imp["errores"] or "[]") + errores)[:500], ensure_ascii=False),
             json.dumps(json.loads(imp["snapshot"] or "[]") + snapshot, ensure_ascii=False), import_id),
        ))
        db.transaccion(self.conn, pasos)
        return {"creadas": creadas, "actualizadas": actualizadas, "ignoradas": ignoradas, "errores": errores}

    def _puntuar(self, t: Ticket) -> None:
        score_ticket(t, self.tax, self.cfg)
        killer = any(str(r).startswith("killer") for r in t.reasons)
        # Lo importaste vos: entra al pipeline salvo que choque con un killer (límites éticos/stack).
        t.verdict = "discard" if killer else "pass"
        t.score_oportunidad, t.score_detalle = calcular(t, self.perfil, self.cfg)
        if killer:
            t.score_oportunidad = 0

    def _empresas(self, tickets: list[Ticket]) -> dict[str, int]:
        """Crea o completa las empresas/clientes del chunk. Devuelve {nombre_norm: id}."""
        datos: dict[str, Ticket] = {}
        for t in tickets:
            n = norm.slug(t.extra.get("empresa"))
            if n:
                datos[n] = t
        if not datos:
            return {}
        pasos = []
        for n, t in datos.items():
            x = t.extra
            pasos.append((
                """INSERT INTO empresas (nombre, nombre_norm, plataforma, verificado, proyectos_previos, calificacion, gasto_total_usd)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(nombre_norm) DO UPDATE SET
                     verificado = COALESCE(excluded.verificado, empresas.verificado),
                     proyectos_previos = COALESCE(excluded.proyectos_previos, empresas.proyectos_previos),
                     calificacion = COALESCE(excluded.calificacion, empresas.calificacion),
                     gasto_total_usd = COALESCE(excluded.gasto_total_usd, empresas.gasto_total_usd)""",
                (x.get("empresa"), n, t.source, x.get("cliente_verificado"), x.get("proyectos_previos_cliente"),
                 x.get("calificacion_cliente"), x.get("gasto_total_cliente_usd")),
            ))
        marcas = ",".join("?" * len(datos))
        pasos.append((f"SELECT id, nombre_norm FROM empresas WHERE nombre_norm IN ({marcas})", tuple(datos)))
        cursores = db.transaccion(self.conn, pasos)
        return {r["nombre_norm"]: int(r["id"]) for r in cursores[-1].fetchall()}

    def deshacer(self, import_id: int) -> dict[str, int]:
        """Borra lo creado por el lote (salvo lo que ya postulaste) y restaura lo actualizado."""
        imp = self.conn.execute("SELECT * FROM importaciones WHERE id = ?", (import_id,)).fetchone()
        if imp is None:
            raise ValueError("importación inexistente")
        if imp["deshecha_at"]:
            raise ValueError("esta importación ya se deshizo")
        trabajadas = self.conn.execute(
            """SELECT COUNT(*) AS n FROM tickets WHERE import_id = ?
               AND (postulado_at IS NOT NULL OR COALESCE(etapa, 'relevada') NOT IN ('relevada', 'interesa', 'descartada'))""",
            (import_id,),
        ).fetchone()["n"]
        filtro = """import_id = ? AND postulado_at IS NULL
                    AND COALESCE(etapa, 'relevada') IN ('relevada', 'interesa', 'descartada')"""
        borradas = self.conn.execute(f"SELECT COUNT(*) AS n FROM tickets WHERE {filtro}", (import_id,)).fetchone()["n"]
        pasos = [
            (f"DELETE FROM eventos WHERE ticket_fp IN (SELECT fingerprint FROM tickets WHERE {filtro})", (import_id,)),
            (f"DELETE FROM tickets WHERE {filtro}", (import_id,)),
        ]
        snapshot = json.loads(imp["snapshot"] or "[]")
        for s in snapshot:
            cols = [k for k in _SNAP if k in s]
            pasos.append((
                f"UPDATE tickets SET {', '.join(f'{k} = ?' for k in cols)} WHERE fingerprint = ?",
                tuple(s[k] for k in cols) + (s["fingerprint"],),
            ))
        pasos.append(("UPDATE importaciones SET deshecha_at = CURRENT_TIMESTAMP WHERE id = ?", (import_id,)))
        db.transaccion(self.conn, pasos)
        return {"borradas": int(borradas), "restauradas": len(snapshot), "conservadas": int(trabajadas)}


def historial(conn: Any, limite: int = 30) -> list:
    return conn.execute(
        """SELECT id, fuente, politica, filas, creadas, actualizadas, ignoradas, con_error, errores,
                  created_at, deshecha_at FROM importaciones ORDER BY id DESC LIMIT ?""",
        (limite,),
    ).fetchall()


def mapeo_guardado(conn: Any, fuente: str) -> dict[str, str]:
    row = conn.execute("SELECT mapeo FROM mapeos_csv WHERE fuente = ?", (fuente,)).fetchone()
    try:
        return json.loads(row["mapeo"]) if row else {}
    except ValueError:
        return {}
