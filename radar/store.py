"""Persistencia y deduplicación. SQLite local o Turso (ver db.py), mismo SQL."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import db
from .models import Ticket

ESTADOS = ("nuevo", "postulado", "respondido", "ganado", "perdido")

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
    postulado_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_seen ON tickets(seen_at);
CREATE INDEX IF NOT EXISTS idx_estado ON tickets(estado);
"""

# Columnas agregadas después de la primera versión: se migran bases existentes.
_COLUMNAS_NUEVAS = {"notas": "TEXT DEFAULT ''", "estado_at": "TEXT", "postulado_at": "TEXT"}

_UPSERT = """INSERT INTO tickets
   (fingerprint, source, title, url, module, score, budget_usd,
    verdict, pitch, engine, payload, notified)
   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
   ON CONFLICT(fingerprint) DO UPDATE SET
     module=excluded.module, score=excluded.score, budget_usd=excluded.budget_usd,
     verdict=excluded.verdict, pitch=excluded.pitch, engine=excluded.engine,
     payload=excluded.payload, notified=excluded.notified"""

_preparadas: set[str] = set()  # bases con esquema ya verificado en este proceso


def _fila(ticket: Ticket, notified: bool) -> tuple:
    return (
        ticket.fingerprint,
        ticket.source,
        ticket.title,
        ticket.url,
        ticket.module,
        ticket.score,
        ticket.budget_usd,
        ticket.verdict,
        ticket.pitch,
        ticket.pitch_engine,
        json.dumps(ticket.to_dict(), ensure_ascii=False),
        int(notified),
    )


def _parse_ts(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "")).replace(tzinfo=None)
    except ValueError:
        return None


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

    def marcar(self, fingerprint: str, estado: str) -> None:
        if estado not in ESTADOS:
            raise ValueError(f"estado inválido: {estado}")
        self.conn.execute(
            """UPDATE tickets SET estado = ?, estado_at = CURRENT_TIMESTAMP,
               postulado_at = CASE WHEN ? != 'nuevo' AND postulado_at IS NULL
                                   THEN CURRENT_TIMESTAMP ELSE postulado_at END
               WHERE fingerprint = ?""",
            (estado, estado, fingerprint),
        )
        self.conn.commit()

    def set_notas(self, fingerprint: str, notas: str) -> None:
        self.conn.execute("UPDATE tickets SET notas = ? WHERE fingerprint = ?", (notas[:4000], fingerprint))
        self.conn.commit()

    def set_pitch(self, fingerprint: str, pitch: str, engine: str) -> None:
        self.conn.execute(
            "UPDATE tickets SET pitch = ?, engine = ? WHERE fingerprint = ?", (pitch, engine, fingerprint)
        )
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
            "SELECT * FROM tickets WHERE url = ? ORDER BY seen_at DESC LIMIT 1", (url,)
        ).fetchone()

    def all_tickets(self):
        return self.conn.execute("SELECT * FROM tickets ORDER BY seen_at DESC").fetchall()

    def pipeline(self) -> dict[str, list]:
        """Tickets que pasaron el filtro (o que ya se trabajaron), agrupados por estado."""
        rows = self.conn.execute(
            """SELECT * FROM tickets WHERE verdict = 'pass' OR estado != 'nuevo'
               ORDER BY score DESC, seen_at DESC"""
        ).fetchall()
        out: dict[str, list] = {e: [] for e in ESTADOS}
        for r in rows:
            out.setdefault(r["estado"] or "nuevo", []).append(r)
        return out

    def revisar(self, min_score: int, limite: int = 25) -> list:
        """Descartados por poco que valen una mirada: score alto, sin killer ni piso de presupuesto."""
        rows = self.conn.execute(
            """SELECT * FROM tickets WHERE verdict = 'discard' AND estado = 'nuevo' AND score >= ?
               ORDER BY score DESC, seen_at DESC LIMIT ?""",
            (min_score, limite * 3),
        ).fetchall()
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

    def stats(self) -> dict[str, int]:
        row = self.conn.execute(
            """SELECT
                 COUNT(*) AS total,
                 SUM(CASE WHEN verdict='pass' THEN 1 ELSE 0 END) AS aprobados,
                 SUM(CASE WHEN notified=1 THEN 1 ELSE 0 END) AS notificados,
                 SUM(CASE WHEN postulado_at IS NOT NULL THEN 1 ELSE 0 END) AS postulados
               FROM tickets"""
        ).fetchone()
        return {k: (row[k] or 0) for k in row.keys()}

    def metricas(self, objetivo_semanal: int = 5, meta_mensual_usd: int = 900) -> dict[str, Any]:
        """KPIs del CRM: propuestas de los últimos 7 días, respuestas, cierres, racha diaria."""
        ahora = datetime.now(timezone.utc).replace(tzinfo=None)
        rows = self.conn.execute(
            """SELECT estado, postulado_at, estado_at, budget_usd, verdict FROM tickets
               WHERE postulado_at IS NOT NULL OR verdict = 'pass'"""
        ).fetchall()

        enviadas = [r for r in rows if r["postulado_at"]]
        semana = [r for r in enviadas if (_parse_ts(r["postulado_at"]) or ahora) >= ahora - timedelta(days=7)]
        respondidas = [r for r in enviadas if r["estado"] in ("respondido", "ganado")]
        ganados = [r for r in enviadas if r["estado"] == "ganado"]
        mes = ahora.strftime("%Y-%m")
        facturado = sum(
            (r["budget_usd"] or 0) for r in ganados if (r["estado_at"] or "").startswith(mes)
        )

        dias = {d.date() for d in (_parse_ts(r["postulado_at"]) for r in enviadas) if d}
        dia, racha = ahora.date(), 0
        if dia not in dias:  # hoy todavía no postulaste: la racha no se corta hasta mañana
            dia -= timedelta(days=1)
        while dia in dias:
            racha += 1
            dia -= timedelta(days=1)

        return {
            "pendientes": sum(1 for r in rows if r["verdict"] == "pass" and r["estado"] == "nuevo"),
            "enviadas_7d": len(semana),
            "objetivo_semanal": objetivo_semanal,
            "enviadas_total": len(enviadas),
            "respondidas": len(respondidas),
            "tasa_respuesta": round(100 * len(respondidas) / len(enviadas)) if enviadas else 0,
            "ganados": len(ganados),
            "facturado_mes_usd": facturado,
            "meta_mensual_usd": meta_mensual_usd,
            "racha_dias": racha,
        }

    def close(self) -> None:
        self.conn.close()
