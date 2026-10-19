"""Copia de seguridad de la base Turso a un SQLite local (solo lectura sobre Turso).

  python scripts/backup_turso.py                 # -> data/backup_AAAAMMDD_HHMM.sqlite
  python scripts/backup_turso.py destino.sqlite

Correlo antes de cualquier migración en producción. Copia todas las tablas con sus filas;
los índices se recrean solos al abrir la copia con el Store.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import config, db  # noqa: E402,F401  (config carga el .env)


def main() -> int:
    if not db.remoto_configurado():
        print("Faltan TURSO_DATABASE_URL / TURSO_AUTH_TOKEN: no hay base remota que copiar.")
        return 1
    raiz = Path(__file__).resolve().parent.parent
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else raiz / "data" / f"backup_{datetime.now():%Y%m%d_%H%M}.sqlite"
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        print(f"{destino} ya existe: elegí otro nombre.")
        return 1
    remoto = db.connect("")
    tablas = remoto.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '_litestream%'"
    ).fetchall()
    local = sqlite3.connect(destino)
    for t in tablas:
        local.execute(t["sql"])
        filas = remoto.execute(f'SELECT * FROM "{t["name"]}"').fetchall()
        if filas:
            marcas = ",".join("?" * len(filas[0]))
            local.executemany(f'INSERT INTO "{t["name"]}" VALUES ({marcas})', [tuple(f) for f in filas])
        print(f"  {t['name']}: {len(filas)} filas")
    local.commit()
    local.close()
    print(f"Backup listo: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
