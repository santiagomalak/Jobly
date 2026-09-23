"""Persistencia y deduplicación (SQLite, cero dependencias)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import Ticket

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
    estado      TEXT DEFAULT 'nuevo'      -- nuevo|postulado|respondido|ganado|perdido
);
CREATE INDEX IF NOT EXISTS idx_seen ON tickets(seen_at);
CREATE INDEX IF NOT EXISTS idx_estado ON tickets(estado);
"""


class Store:
    def __init__(self, db_path: str | Path):
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def is_known(self, ticket: Ticket) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM tickets WHERE fingerprint = ?", (ticket.fingerprint,)
        )
        return cur.fetchone() is not None

    def save(self, ticket: Ticket, notified: bool = False) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO tickets
               (fingerprint, source, title, url, module, score, budget_usd,
                verdict, pitch, engine, payload, notified)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
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
            ),
        )
        self.conn.commit()

    def stats(self) -> dict[str, int]:
        cur = self.conn.execute(
            """SELECT
                 COUNT(*) AS total,
                 SUM(CASE WHEN verdict='pass' THEN 1 ELSE 0 END) AS aprobados,
                 SUM(CASE WHEN notified=1 THEN 1 ELSE 0 END) AS notificados,
                 SUM(CASE WHEN estado='postulado' THEN 1 ELSE 0 END) AS postulados
               FROM tickets"""
        )
        row = cur.fetchone()
        return {k: (row[k] or 0) for k in row.keys()}

    def marcar(self, fingerprint: str, estado: str) -> None:
        self.conn.execute(
            "UPDATE tickets SET estado = ? WHERE fingerprint = ?", (estado, fingerprint)
        )
        self.conn.commit()

    def get(self, fingerprint: str) -> sqlite3.Row | None:
        cur = self.conn.execute(
            "SELECT * FROM tickets WHERE fingerprint = ?", (fingerprint,)
        )
        return cur.fetchone()

    def get_by_url(self, url: str) -> sqlite3.Row | None:
        cur = self.conn.execute(
            "SELECT * FROM tickets WHERE url = ? ORDER BY seen_at DESC LIMIT 1", (url,)
        )
        return cur.fetchone()

    def all_tickets(self) -> list[sqlite3.Row]:
        cur = self.conn.execute("SELECT * FROM tickets ORDER BY seen_at DESC")
        return cur.fetchall()

    def close(self) -> None:
        self.conn.close()
