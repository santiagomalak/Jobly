"""Conexión a la base: SQLite local por defecto, Turso (libSQL por HTTP) si hay credenciales.

Vercel no guarda archivos entre ejecuciones, así que el CRM web y el cron de GitHub Actions
comparten una base hosteada. Turso habla SQLite, por eso el SQL de store.py no cambia.
Se usa su API HTTP (/v2/pipeline) con `requests`: sin dependencias nativas ni drivers.

Variables: TURSO_DATABASE_URL (libsql://nombre-org.turso.io) y TURSO_AUTH_TOKEN.
"""
from __future__ import annotations

import base64
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Sequence

import requests

_LOTE = 40  # sentencias por request al ejecutar en batch


class Row:
    """Fila con acceso por nombre o posición, como sqlite3.Row."""

    def __init__(self, cols: Sequence[str], vals: Sequence[Any]):
        self._cols = list(cols)
        self._vals = list(vals)

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._vals[key]
        return self._vals[self._cols.index(key)]

    def keys(self) -> list[str]:
        return list(self._cols)

    def __iter__(self):
        return iter(self._vals)

    def __len__(self) -> int:
        return len(self._vals)


class _Cursor:
    def __init__(self, rows: list[Row]):
        self._rows = rows

    def fetchone(self) -> Row | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[Row]:
        return list(self._rows)


def _codificar(valor: Any) -> dict[str, Any]:
    if valor is None:
        return {"type": "null"}
    if isinstance(valor, bool):
        return {"type": "integer", "value": str(int(valor))}
    if isinstance(valor, int):
        return {"type": "integer", "value": str(valor)}
    if isinstance(valor, float):
        return {"type": "float", "value": valor}
    if isinstance(valor, (bytes, bytearray)):
        return {"type": "blob", "base64": base64.b64encode(bytes(valor)).decode()}
    return {"type": "text", "value": str(valor)}


def _decodificar(celda: dict[str, Any]) -> Any:
    tipo = celda.get("type")
    if tipo == "null":
        return None
    if tipo == "integer":
        return int(celda["value"])
    if tipo == "float":
        return float(celda["value"])
    if tipo == "blob":
        return base64.b64decode(celda.get("base64", ""))
    return celda.get("value")


class TursoConnection:
    """Subconjunto de la API de sqlite3.Connection que usa store.py."""

    def __init__(self, url: str, token: str, timeout: int = 20):
        base = re.sub(r"^libsql://", "https://", url.strip()).rstrip("/")
        self._endpoint = f"{base}/v2/pipeline"
        self._headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self._timeout = timeout

    def _pipeline(self, sentencias: list[tuple[str, Sequence[Any]]]) -> list[_Cursor]:
        pedidos = [
            {"type": "execute", "stmt": {"sql": sql, "args": [_codificar(a) for a in args]}}
            for sql, args in sentencias
        ]
        pedidos.append({"type": "close"})
        r = requests.post(
            self._endpoint, json={"requests": pedidos}, headers=self._headers, timeout=self._timeout
        )
        r.raise_for_status()
        cursores: list[_Cursor] = []
        for res in r.json().get("results", [])[: len(sentencias)]:
            if res.get("type") == "error":
                raise RuntimeError(f"Turso: {res.get('error', {}).get('message', res)}")
            data = res["response"]["result"]
            cols = [c["name"] for c in data.get("cols", [])]
            cursores.append(
                _Cursor([Row(cols, [_decodificar(c) for c in fila]) for fila in data.get("rows", [])])
            )
        return cursores

    def execute(self, sql: str, params: Sequence[Any] = ()) -> _Cursor:
        return self._pipeline([(sql, params)])[0]

    def executemany(self, sql: str, filas: Sequence[Sequence[Any]]) -> None:
        for i in range(0, len(filas), _LOTE):
            self._pipeline([(sql, f) for f in filas[i : i + _LOTE]])

    def executescript(self, script: str) -> None:
        sin_comentarios = re.sub(r"--[^\n]*", "", script)
        sentencias = [(s.strip(), ()) for s in sin_comentarios.split(";") if s.strip()]
        for i in range(0, len(sentencias), _LOTE):
            self._pipeline(sentencias[i : i + _LOTE])

    def commit(self) -> None:  # cada request se confirma solo
        pass

    def close(self) -> None:
        pass


def remoto_configurado() -> bool:
    return bool(os.environ.get("TURSO_DATABASE_URL") and os.environ.get("TURSO_AUTH_TOKEN"))


def connect(db_path: str | Path):
    if remoto_configurado():
        return TursoConnection(os.environ["TURSO_DATABASE_URL"], os.environ["TURSO_AUTH_TOKEN"])
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
