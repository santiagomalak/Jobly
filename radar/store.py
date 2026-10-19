"""Persistencia y deduplicación. SQLite local o Turso (ver db.py), mismo SQL.

El esquema base vive acá (SCHEMA + columnas legadas); todo lo posterior son migraciones
versionadas en radar/migrations/ (ver migraciones.py), que se aplican solas al abrir el Store.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from . import db, migraciones
from . import etapas as et
from . import normalizar as norm
from .models import Ticket

ESTADOS = ("nuevo", "postulado", "respondido", "ganado", "perdido")  # legado: CLI y API vieja

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    fingerprint TEXT PRIMARY KEY,
    source      TEXT,
    title       TEXT,
    url         TEXT,
    module      TEXT,
    score       INTEGER,
    budget_usd  INTEGER,
    verdict     TEXT,
    pitch       TEXT,
    engine      TEXT,
    payload     TEXT,
    seen_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    notified    INTEGER DEFAULT 0,
    estado      TEXT DEFAULT 'nuevo',
    notas       TEXT DEFAULT '',
    estado_at   TEXT,
    postulado_at TEXT,
    seguimientos INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_seen ON tickets(seen_at);
CREATE INDEX IF NOT EXISTS idx_estado ON tickets(estado);
"""

# Columnas agregadas antes de que existieran las migraciones versionadas.
_COLUMNAS_NUEVAS = {
    "notas": "TEXT DEFAULT ''",
    "estado_at": "TEXT",
    "postulado_at": "TEXT",
    "seguimientos": "INTEGER DEFAULT 0",
    "costo_usd": "INTEGER DEFAULT 0",
}

# Re-guardar un ticket actualiza el análisis, nunca lo que trabajaste (etapa, notas, fechas).
_UPSERT = """INSERT INTO tickets
   (fingerprint, source, title, url, module, score, budget_usd, verdict, pitch, engine, payload, notified,
    tipo, url_norm, clave_norm, score_oportunidad, score_detalle, presupuesto_min, presupuesto_max,
    moneda, periodo_pago, duracion_dias, idioma, propuestas_recibidas, import_id, empresa_id, etapa)
   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'relevada')
   ON CONFLICT(fingerprint) DO UPDATE SET
     module=excluded.module, score=excluded.score, budget_usd=excluded.budget_usd,
     verdict=excluded.verdict, pitch=excluded.pitch, engine=excluded.engine,
     payload=excluded.payload, notified=excluded.notified, tipo=excluded.tipo,
     url_norm=excluded.url_norm, clave_norm=excluded.clave_norm,
     score_oportunidad=excluded.score_oportunidad, score_detalle=excluded.score_detalle,
     presupuesto_min=excluded.presupuesto_min, presupuesto_max=excluded.presupuesto_max,
     moneda=excluded.moneda, periodo_pago=excluded.periodo_pago, duracion_dias=excluded.duracion_dias,
     idioma=excluded.idioma, propuestas_recibidas=excluded.propuestas_recibidas,
     empresa_id=COALESCE(excluded.empresa_id, tickets.empresa_id)"""

# Columnas livianas para listas (sin payload ni pitch).
_COLS_LISTA = """fingerprint, title, source, module, score, score_oportunidad, budget_usd, notas, etapa,
    estado, tipo, postulado_at, estado_at, seguimientos, proxima_accion, proxima_accion_at, costo_usd,
    verdict, seen_at, presupuesto_min, presupuesto_max, moneda, periodo_pago, url"""

_preparadas: set[str] = set()  # bases con esquema ya verificado en este proceso


def _tipo(ticket: Ticket) -> str:
    from .oportunidad import tipo_de  # import diferido: oportunidad importa fit -> memory

    return tipo_de(ticket)


def _fila(ticket: Ticket, notified: bool, import_id: int | None = None, empresa_id: int | None = None) -> tuple:
    x = ticket.extra
    return (
        ticket.fingerprint, ticket.source, ticket.title, ticket.url, ticket.module, ticket.score,
        ticket.budget_usd, ticket.verdict, ticket.pitch, ticket.pitch_engine,
        json.dumps(ticket.to_dict(), ensure_ascii=False), int(notified),
        _tipo(ticket), norm.url_norm(ticket.url), norm.clave(x.get("empresa"), ticket.title) or None,
        ticket.score_oportunidad,
        json.dumps(ticket.score_detalle, ensure_ascii=False) if ticket.score_detalle else None,
        x.get("presupuesto_min"), x.get("presupuesto_max"), x.get("moneda") or None,
        x.get("periodo_pago") or None, x.get("duracion_dias"), x.get("idioma") or None,
        x.get("propuestas_recibidas"), import_id, empresa_id,
    )


def _parse_ts(valor: str | None) -> datetime | None:
    """Fechas de la base (UTC, 'AAAA-MM-DD HH:MM:SS' o ISO) -> datetime UTC naive."""
    if not valor:
        return None
    try:
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=None)


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def etapa_de(row: Any) -> str:
    """Etapa de una fila; si la columna está vacía (fila vieja), se deduce del estado."""
    try:
        e = row["etapa"]
    except (IndexError, KeyError, ValueError):
        e = None
    if e in et.ETAPAS:
        return e
    estado = row["estado"] or "nuevo"
    if estado == "perdido" and not row["postulado_at"]:
        return "descartada"
    return et.de_estado(estado)


def enviada(row: Any) -> bool:
    return bool(row["postulado_at"]) and etapa_de(row) in et.ENVIADAS


class Store:
    def __init__(self, db_path: str | Path):
        self.conn = db.connect(db_path)
        clave = "turso" if db.remoto_configurado() else str(Path(db_path).resolve())
        if clave not in _preparadas:
            self.conn.executescript(SCHEMA)
            existentes = {r["name"] for r in self.conn.execute("PRAGMA table_info(tickets)").fetchall()}
            for col, ddl in _COLUMNAS_NUEVAS.items():
                if col not in existentes:
                    self.conn.execute(f"ALTER TABLE tickets ADD COLUMN {col} {ddl}")
            self.conn.commit()
            migraciones.aplicar(self.conn)
            _preparadas.add(clave)

    # ---------- escritura ----------
    def save(self, ticket: Ticket, notified: bool = False) -> None:
        self.conn.execute(_UPSERT, _fila(ticket, notified))
        self.conn.commit()

    def save_many(self, items: list[tuple[Ticket, bool]]) -> None:
        if not items:
            return
        self.conn.executemany(_UPSERT, [_fila(t, n) for t, n in items])
        self.conn.commit()

    def mover(self, fingerprint: str, etapa: str, detalle: str = "") -> str:
        """Cambia la etapa, registra el evento y agenda la próxima acción. Devuelve la etapa previa."""
        if etapa not in et.ETAPAS:
            raise ValueError(f"etapa inválida: {etapa}")
        row = self.get(fingerprint)
        if row is None:
            raise KeyError(fingerprint)
        previa = etapa_de(row)
        ahora = _ahora()
        tipo = row["tipo"] or "freelance"

        accion, accion_at = row["proxima_accion"], row["proxima_accion_at"]
        if etapa == "postulada" and previa != "postulada":
            desde = _parse_ts(row["postulado_at"]) or ahora
            accion, accion_at = "Seguimiento 1", _ts(desde + timedelta(days=et.dias_seguimiento(tipo)[0]))
        elif etapa == "interesa" and not accion:
            accion, accion_at = "Postular", _ts(ahora)
        elif etapa in et.CERRADAS or etapa == "relevada":
            accion, accion_at = None, None

        db.transaccion(self.conn, [
            ("""UPDATE tickets SET etapa = ?, estado = ?, estado_at = ?,
                  postulado_at = CASE WHEN ? AND postulado_at IS NULL THEN ? ELSE postulado_at END,
                  proxima_accion = ?, proxima_accion_at = ?
                WHERE fingerprint = ?""",
             (etapa, et.a_estado(etapa), _ts(ahora), int(etapa in et.ENVIADAS), _ts(ahora),
              accion, accion_at, fingerprint)),
            ("INSERT INTO eventos (ticket_fp, tipo, de_etapa, a_etapa, detalle, fecha) VALUES (?,?,?,?,?,?)",
             (fingerprint, "cambio_etapa", previa, etapa, detalle[:500], _ts(ahora))),
        ])
        return previa

    def marcar(self, fingerprint: str, estado: str) -> None:
        """API legada (CLI, import de postulaciones): estado de 5 valores -> etapa."""
        if estado not in ESTADOS:
            raise ValueError(f"estado inválido: {estado}")
        etapa = et.de_estado(estado)
        if estado == "perdido":
            row = self.get(fingerprint)
            etapa = "rechazada" if row is not None and row["postulado_at"] else "descartada"
        self.mover(fingerprint, etapa)

    def set_notas(self, fingerprint: str, notas: str) -> None:
        self.conn.execute("UPDATE tickets SET notas = ? WHERE fingerprint = ?", (notas[:4000], fingerprint))
        self.conn.commit()

    def set_costo(self, fingerprint: str, costo_usd: int) -> None:
        """Gastos/costos reales imputados al proyecto (infra, herramientas, comisiones):
        se resta del ingreso para ver rentabilidad neta, no solo facturación bruta."""
        self.conn.execute(
            "UPDATE tickets SET costo_usd = ? WHERE fingerprint = ?", (max(0, int(costo_usd)), fingerprint)
        )
        self.conn.commit()

    def set_proxima_accion(self, fingerprint: str, texto: str, fecha: str | None) -> None:
        texto = texto.strip()[:200]
        db.transaccion(self.conn, [
            ("UPDATE tickets SET proxima_accion = ?, proxima_accion_at = ? WHERE fingerprint = ?",
             (texto or None, fecha if texto else None, fingerprint)),
            ("INSERT INTO eventos (ticket_fp, tipo, detalle, fecha) VALUES (?,?,?,?)",
             (fingerprint, "accion", f"{texto} ({fecha[:10]})" if texto and fecha else (texto or "acción borrada"), _ts(_ahora()))),
        ])

    def agregar_evento(self, fingerprint: str, tipo: str, detalle: str) -> None:
        self.conn.execute(
            "INSERT INTO eventos (ticket_fp, tipo, detalle, fecha) VALUES (?,?,?,?)",
            (fingerprint, tipo, detalle[:1000], _ts(_ahora())),
        )
        self.conn.commit()

    def registrar_seguimiento(self, fingerprint: str) -> int:
        """Anota que enviaste un seguimiento y agenda el próximo paso. Devuelve cuántos van (tope 2)."""
        row = self.get(fingerprint)
        if row is None:
            return 0
        hechos = min(int(row["seguimientos"] or 0) + 1, 2)
        d1, d2 = et.dias_seguimiento(row["tipo"])
        desde = _parse_ts(row["postulado_at"]) or _ahora()
        if hechos == 1:
            accion, cuando = "Seguimiento 2", desde + timedelta(days=d2)
        else:
            accion, cuando = "Cerrar si no responden", desde + timedelta(days=d2 + et.CIERRE.get(row["tipo"] or "freelance", 4))
        db.transaccion(self.conn, [
            ("UPDATE tickets SET seguimientos = ?, proxima_accion = ?, proxima_accion_at = ? WHERE fingerprint = ?",
             (hechos, accion, _ts(cuando), fingerprint)),
            ("INSERT INTO eventos (ticket_fp, tipo, detalle, fecha) VALUES (?,?,?,?)",
             (fingerprint, "followup", f"Seguimiento {hechos} enviado", _ts(_ahora()))),
        ])
        return hechos

    def _vencidos(self, rows: list, ahora: datetime) -> list[tuple[Any, int, float]]:
        out = []
        for r in rows:
            if etapa_de(r) != "postulada":
                continue
            hechos = int(r["seguimientos"] or 0)
            desde = _parse_ts(r["postulado_at"])
            dias = et.dias_seguimiento(r["tipo"])
            if hechos < 2 and desde:
                atraso = (ahora - desde).total_seconds() / 86400 - dias[hechos]
                if atraso >= 0:
                    out.append((r, hechos + 1, atraso))
        return sorted(out, key=lambda x: -x[2])

    def seguimientos_pendientes(self) -> list[tuple[Any, int, float]]:
        """Postuladas sin respuesta cuyo próximo seguimiento ya venció: [(fila, número, días de atraso)]."""
        rows = self.conn.execute(
            f"SELECT {_COLS_LISTA} FROM tickets WHERE (etapa = 'postulada' OR (etapa IS NULL AND estado = 'postulado')) AND postulado_at IS NOT NULL"
        ).fetchall()
        return self._vencidos(rows, _ahora())

    def cerrar_sin_respuesta(self) -> int:
        """Postuladas con los 2 seguimientos hechos y sin respuesta pasado el plazo -> sin_respuesta."""
        ahora = _ahora()
        rows = self.conn.execute(
            "SELECT fingerprint, tipo, postulado_at FROM tickets WHERE etapa = 'postulada' AND seguimientos >= 2"
        ).fetchall()
        cerradas = 0
        for r in rows:
            desde = _parse_ts(r["postulado_at"])
            tipo = r["tipo"] or "freelance"
            plazo = et.dias_seguimiento(tipo)[1] + et.CIERRE.get(tipo, 4)
            if desde and (ahora - desde).days >= plazo:
                self.mover(r["fingerprint"], "sin_respuesta", "cerrada sola: 2 seguimientos sin respuesta")
                cerradas += 1
        return cerradas

    def set_pitch(self, fingerprint: str, pitch: str, engine: str) -> None:
        self.conn.execute(
            "UPDATE tickets SET pitch = ?, engine = ? WHERE fingerprint = ?", (pitch, engine, fingerprint)
        )
        self.conn.commit()

    def set_oportunidad(self, cambios: list[tuple[int, list, str]]) -> None:
        """[(score, detalle, fingerprint)] calculados fuera (oportunidad.calcular)."""
        if cambios:
            self.conn.executemany(
                "UPDATE tickets SET score_oportunidad = ?, score_detalle = ? WHERE fingerprint = ?",
                [(s, json.dumps(d, ensure_ascii=False), fp) for s, d, fp in cambios],
            )
            self.conn.commit()

    # ---------- ingresos ----------
    def agregar_ingreso(self, fingerprint: str | None, monto_usd: int, estado: str, fecha: str, detalle: str = "") -> None:
        if estado not in ("acordado", "cobrado"):
            raise ValueError("estado de ingreso inválido")
        pasos = [("INSERT INTO ingresos (ticket_fp, monto_usd, estado, fecha, detalle) VALUES (?,?,?,?,?)",
                  (fingerprint, max(0, int(monto_usd)), estado, fecha, detalle[:300]))]
        if fingerprint:
            pasos.append(("INSERT INTO eventos (ticket_fp, tipo, detalle, fecha) VALUES (?,?,?,?)",
                          (fingerprint, "nota", f"Ingreso {estado}: USD {int(monto_usd)}", _ts(_ahora()))))
        db.transaccion(self.conn, pasos)

    def marcar_cobrado(self, ingreso_id: int) -> None:
        self.conn.execute("UPDATE ingresos SET estado = 'cobrado' WHERE id = ?", (ingreso_id,))
        self.conn.commit()

    def borrar_ingreso(self, ingreso_id: int) -> None:
        self.conn.execute("DELETE FROM ingresos WHERE id = ?", (ingreso_id,))
        self.conn.commit()

    # ---------- lectura ----------
    def is_known(self, ticket: Ticket) -> bool:
        cur = self.conn.execute("SELECT 1 FROM tickets WHERE fingerprint = ?", (ticket.fingerprint,))
        return cur.fetchone() is not None

    def known_set(self) -> set[str]:
        return {r["fingerprint"] for r in self.conn.execute("SELECT fingerprint FROM tickets").fetchall()}

    def get(self, fingerprint: str):
        return self.conn.execute("SELECT * FROM tickets WHERE fingerprint = ?", (fingerprint,)).fetchone()

    def get_by_url(self, url: str):
        return self.conn.execute(
            "SELECT * FROM tickets WHERE url_norm = ? OR url = ? ORDER BY seen_at DESC LIMIT 1",
            (norm.url_norm(url), url),
        ).fetchone()

    def detalle(self, fingerprint: str) -> dict[str, Any]:
        """Todo lo de una postulación en un viaje: fila, timeline e ingresos."""
        fila, eventos, ingresos = db.batch(self.conn, [
            ("SELECT * FROM tickets WHERE fingerprint = ?", (fingerprint,)),
            ("SELECT * FROM eventos WHERE ticket_fp = ? ORDER BY fecha DESC, id DESC LIMIT 100", (fingerprint,)),
            ("SELECT * FROM ingresos WHERE ticket_fp = ? ORDER BY fecha DESC, id DESC", (fingerprint,)),
        ])
        return {"row": fila.fetchone(), "eventos": eventos.fetchall(), "ingresos": ingresos.fetchall()}

    def all_tickets(self):
        return self.conn.execute("SELECT * FROM tickets ORDER BY seen_at DESC").fetchall()

    def pipeline(self) -> dict[str, list]:
        """Legado: tickets que pasaron el filtro (o ya trabajados), agrupados por estado de 5 valores."""
        rows = self.conn.execute(
            f"""SELECT {_COLS_LISTA} FROM tickets WHERE verdict = 'pass' OR estado != 'nuevo'
               ORDER BY score DESC, seen_at DESC"""
        ).fetchall()
        out: dict[str, list] = {e: [] for e in ESTADOS}
        for r in rows:
            out.setdefault(r["estado"] or "nuevo", []).append(r)
        return out

    @staticmethod
    def _filtrar_revisar(rows: list, limite: int) -> list:
        out = []
        for r in rows:
            try:
                razones = json.loads(r["payload"] or "{}").get("reasons", [])
            except ValueError:
                razones = []
            if any(str(x).startswith("killer") or "< piso" in str(x) for x in razones):
                continue
            out.append(r)
        return out[:limite]

    def revisar(self, min_score: int, limite: int = 25) -> list:
        """Descartados por poco que valen una mirada: score alto, sin killer ni piso de presupuesto."""
        rows = self.conn.execute(
            """SELECT * FROM tickets WHERE verdict = 'discard' AND estado = 'nuevo' AND score >= ?
               ORDER BY score DESC, seen_at DESC LIMIT ?""",
            (min_score, limite * 3),
        ).fetchall()
        return self._filtrar_revisar(rows, limite)

    def stats(self) -> dict[str, int]:
        row = self.conn.execute(
            """SELECT
                 COUNT(*) AS total,
                 SUM(CASE WHEN verdict='pass' THEN 1 ELSE 0 END) AS aprobados,
                 SUM(CASE WHEN notified=1 THEN 1 ELSE 0 END) AS notificados,
                 SUM(CASE WHEN postulado_at IS NOT NULL AND COALESCE(etapa, '') != 'descartada' THEN 1 ELSE 0 END) AS postulados
               FROM tickets"""
        ).fetchone()
        return {k: (row[k] or 0) for k in row.keys()}

    @staticmethod
    def _metricas(rows: list, objetivo_semanal: int, meta_mensual_usd: int, ahora: datetime) -> dict[str, Any]:
        enviadas = [r for r in rows if enviada(r)]
        semana = [r for r in enviadas if (_parse_ts(r["postulado_at"]) or ahora) >= ahora - timedelta(days=7)]
        respondidas = [r for r in enviadas if etapa_de(r) in et.RESPONDIDAS]
        ganados = [r for r in enviadas if etapa_de(r) == "ganada"]
        mes = (ahora + timedelta(hours=-3)).strftime("%Y-%m")
        ganados_mes = [r for r in ganados if (_ts_art(r["estado_at"]) or "").startswith(mes)]
        facturado = sum((r["budget_usd"] or 0) for r in ganados_mes)
        costos = sum((r["costo_usd"] or 0) for r in ganados_mes)

        # Racha en días calendario de Argentina
        dias = {d.date() for d in ((_parse_ts(r["postulado_at"]) or ahora) - timedelta(hours=3) for r in enviadas)}
        dia, racha = (ahora - timedelta(hours=3)).date(), 0
        if dia not in dias:  # hoy todavía no postulaste: la racha no se corta hasta mañana
            dia -= timedelta(days=1)
        while dia in dias:
            racha += 1
            dia -= timedelta(days=1)
        hoy = (ahora - timedelta(hours=3)).date()

        return {
            "pendientes": sum(1 for r in rows if r["verdict"] == "pass" and etapa_de(r) in ("relevada", "interesa")),
            "enviadas_7d": len(semana),
            "enviadas_hoy": sum(1 for r in enviadas if ((_parse_ts(r["postulado_at"]) or ahora) - timedelta(hours=3)).date() == hoy),
            "objetivo_semanal": objetivo_semanal,
            "enviadas_total": len(enviadas),
            "respondidas": len(respondidas),
            "tasa_respuesta": round(100 * len(respondidas) / len(enviadas)) if enviadas else 0,
            "ganados": len(ganados),
            "facturado_mes_usd": facturado,
            "costos_mes_usd": costos,
            "neto_mes_usd": facturado - costos,
            "meta_mensual_usd": meta_mensual_usd,
            "racha_dias": racha,
        }

    def metricas(self, objetivo_semanal: int = 5, meta_mensual_usd: int = 900) -> dict[str, Any]:
        """KPIs del CRM: propuestas de los últimos 7 días, respuestas, cierres, racha diaria."""
        rows = self.conn.execute(
            f"SELECT {_COLS_LISTA} FROM tickets WHERE postulado_at IS NOT NULL OR verdict = 'pass'"
        ).fetchall()
        return self._metricas(rows, objetivo_semanal, meta_mensual_usd, _ahora())

    def tablero(self, cfg: dict[str, Any], completar: Callable[[list], None] | None = None) -> dict[str, Any]:
        """Todo lo de la home en UN viaje a la base: pipeline, para revisar, ingresos del mes.
        `completar` recibe las filas sin score de oportunidad para calcularlo (y persistirlo)."""
        ahora = _ahora()
        inicio_mes = (ahora - timedelta(hours=3)).strftime("%Y-%m-01")
        minimo = int(cfg.get("review_score", 30))
        pipe, rev, ing = db.batch(self.conn, [
            (f"""SELECT {_COLS_LISTA} FROM tickets
                 WHERE verdict = 'pass' OR postulado_at IS NOT NULL OR COALESCE(etapa, 'relevada') != 'relevada'
                 ORDER BY COALESCE(score_oportunidad, -1) DESC, score DESC, seen_at DESC""", ()),
            ("""SELECT * FROM tickets WHERE verdict = 'discard' AND estado = 'nuevo' AND score >= ?
                ORDER BY score DESC, seen_at DESC LIMIT 75""", (minimo,)),
            ("SELECT * FROM ingresos WHERE fecha >= ? ORDER BY fecha DESC", (inicio_mes,)),
        ])
        rows = pipe.fetchall()
        if completar:
            faltan = [r for r in rows if r["score_oportunidad"] is None and etapa_de(r) in ("relevada", "interesa")]
            if faltan:
                completar(faltan)
                rows = self.conn.execute(
                    f"""SELECT {_COLS_LISTA} FROM tickets
                        WHERE verdict = 'pass' OR postulado_at IS NOT NULL OR COALESCE(etapa, 'relevada') != 'relevada'
                        ORDER BY COALESCE(score_oportunidad, -1) DESC, score DESC, seen_at DESC"""
                ).fetchall()
        por_etapa: dict[str, list] = {e: [] for e in et.ETAPAS}
        for r in rows:
            por_etapa[etapa_de(r)].append(r)
        return {
            "rows": rows,
            "por_etapa": por_etapa,
            "revisar": self._filtrar_revisar(rev.fetchall(), 25),
            "ingresos_mes": ing.fetchall(),
            "seguimientos": self._vencidos(rows, ahora),
            "metricas": self._metricas(rows, int(cfg.get("objetivo_semanal", 5)), int(cfg.get("meta_mensual_usd", 900)), ahora),
            "ahora": ahora,
        }

    def payloads(self, fingerprints: list[str]) -> dict[str, dict]:
        if not fingerprints:
            return {}
        marcas = ",".join("?" * len(fingerprints))
        out = {}
        for r in self.conn.execute(f"SELECT fingerprint, payload FROM tickets WHERE fingerprint IN ({marcas})", tuple(fingerprints)).fetchall():
            try:
                out[r["fingerprint"]] = json.loads(r["payload"] or "{}")
            except ValueError:
                out[r["fingerprint"]] = {}
        return out

    def analitica(self, semanas: int = 8) -> dict[str, Any]:
        """Qué convierte: embudo por tipo de trabajo, fuente y tipo (empleo/freelance), más el ritmo
        semanal. "Respuesta" = cualquier etapa posterior a postulada salvo sin respuesta."""
        ahora = _ahora()
        rows = [r for r in self.conn.execute(
            "SELECT module, source, tipo, etapa, estado, postulado_at FROM tickets WHERE postulado_at IS NOT NULL"
        ).fetchall() if enviada(r)]

        def agrupar(campo: str) -> list[dict[str, Any]]:
            grupos: dict[str, dict[str, int]] = {}
            for r in rows:
                g = grupos.setdefault(r[campo] or "—", {"enviadas": 0, "respuestas": 0, "entrevistas": 0, "ganadas": 0})
                e = etapa_de(r)
                g["enviadas"] += 1
                g["respuestas"] += e in et.RESPONDIDAS
                g["entrevistas"] += e in ("entrevista", "oferta", "ganada")
                g["ganadas"] += e == "ganada"
            filas = [
                {"nombre": k, **v, "tasa": round(100 * v["respuestas"] / v["enviadas"])}
                for k, v in grupos.items()
            ]
            return sorted(filas, key=lambda f: (-f["enviadas"], f["nombre"]))

        lunes = ahora.date() - timedelta(days=ahora.weekday())
        cuentas = {lunes - timedelta(weeks=i): 0 for i in range(semanas)}
        for r in rows:
            dt = _parse_ts(r["postulado_at"])
            if dt and (dt.date() - timedelta(days=dt.weekday())) in cuentas:
                cuentas[dt.date() - timedelta(days=dt.weekday())] += 1
        embudo = [
            ("Enviadas", len(rows)),
            ("Con respuesta", sum(etapa_de(r) in et.RESPONDIDAS for r in rows)),
            ("Entrevista / negociación", sum(etapa_de(r) in ("entrevista", "oferta", "ganada") for r in rows)),
            ("Oferta", sum(etapa_de(r) in ("oferta", "ganada") for r in rows)),
            ("Ganadas", sum(etapa_de(r) == "ganada" for r in rows)),
        ]
        return {
            "por_modulo": agrupar("module"),
            "por_fuente": agrupar("source"),
            "por_tipo": agrupar("tipo"),
            "embudo": embudo,
            "semanal": [{"semana": d.strftime("%d/%m"), "n": n} for d, n in sorted(cuentas.items())],
            "total": len(rows),
        }

    def close(self) -> None:
        self.conn.close()


def _ts_art(valor: str | None) -> str | None:
    """Fecha UTC de la base -> 'AAAA-MM-DD HH:MM:SS' en hora de Argentina (para filtrar por mes)."""
    dt = _parse_ts(valor)
    return _ts(dt - timedelta(hours=3)) if dt else None
