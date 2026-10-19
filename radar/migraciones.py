"""Migraciones versionadas: radar/migrations/NNNN_nombre.up.sql y .down.sql.

- Se aplican solas al abrir el Store (cron, CLI y web), en orden y cada una en una transacción
  (todo o nada). Si dos procesos arrancan a la vez, el segundo encuentra la versión ya aplicada.
- `python -m radar.main migrate --down N` revierte hasta dejar la versión N (antes: hacé backup).
- Una migración puede tener un paso posterior en Python (`posterior_N`) para lo que no entra
  en SQL, como normalizar URLs.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Callable

from . import db
from . import normalizar as norm

log = logging.getLogger("radar.migraciones")

DIR = Path(__file__).resolve().parent / "migrations"
_NOMBRE = re.compile(r"^(\d{4})_[a-z0-9_]+\.(up|down)\.sql$")


def disponibles() -> list[tuple[int, Path, Path | None]]:
    """[(versión, up, down)] ordenadas."""
    ups: dict[int, Path] = {}
    downs: dict[int, Path] = {}
    for f in DIR.glob("*.sql"):
        m = _NOMBRE.match(f.name)
        if m:
            (ups if m.group(2) == "up" else downs)[int(m.group(1))] = f
    return [(v, ups[v], downs.get(v)) for v in sorted(ups)]


def _asegurar_tabla(conn: Any) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )


def version_actual(conn: Any) -> int:
    _asegurar_tabla(conn)
    row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    return int(row["v"] or 0) if row else 0


def aplicar(conn: Any) -> list[int]:
    """Aplica las migraciones pendientes. Devuelve las versiones aplicadas."""
    hechas = version_actual(conn)
    aplicadas: list[int] = []
    for version, up, _ in disponibles():
        if version <= hechas:
            continue
        pasos = [(s, ()) for s in db.sentencias(up.read_text(encoding="utf-8"))]
        pasos.append(("INSERT INTO schema_migrations(version) VALUES (?)", (version,)))
        try:
            db.transaccion(conn, pasos)
        except Exception:
            if version_actual(conn) >= version:  # otro proceso la aplicó en paralelo
                continue
            raise
        posterior = _POSTERIORES.get(version)
        if posterior:
            posterior(conn)
        log.info("migración %04d aplicada", version)
        aplicadas.append(version)
    return aplicadas


def revertir(conn: Any, hasta: int) -> list[int]:
    """Corre los .down.sql de las versiones > `hasta`, de la más nueva a la más vieja."""
    revertidas: list[int] = []
    actual = version_actual(conn)
    for version, _, down in reversed(disponibles()):
        if version <= hasta or version > actual:
            continue
        if down is None:
            raise RuntimeError(f"La migración {version:04d} no tiene .down.sql")
        pasos = [(s, ()) for s in db.sentencias(down.read_text(encoding="utf-8"))]
        pasos.append(("DELETE FROM schema_migrations WHERE version = ?", (version,)))
        db.transaccion(conn, pasos)
        log.info("migración %04d revertida", version)
        revertidas.append(version)
    return revertidas


# ---------------------------------------------------------------- pasos posteriores
def _posterior_1(conn: Any) -> None:
    """url_norm y clave_norm para dedupe (la normalización no entra en SQL)."""
    filas = conn.execute("SELECT fingerprint, url, title, payload FROM tickets").fetchall()
    cambios = []
    for r in filas:
        try:
            empresa = (json.loads(r["payload"] or "{}").get("extra") or {}).get("empresa", "")
        except ValueError:
            empresa = ""
        cambios.append((norm.url_norm(r["url"]), norm.clave(empresa, r["title"]) or None, r["fingerprint"]))
    if cambios:
        conn.executemany("UPDATE tickets SET url_norm = ?, clave_norm = ? WHERE fingerprint = ?", cambios)


_POSTERIORES: dict[int, Callable[[Any], None]] = {1: _posterior_1}
