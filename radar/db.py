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


def _cursor(data: dict[str, Any]) -> _Cursor:
    cols = [c["name"] for c in data.get("cols", [])]
    return _Cursor([Row(cols, [_decodificar(c) for c in fila]) for fila in data.get("rows", [])])


def _stmt(sql: str, args: Sequence[Any]) -> dict[str, Any]:
    return {"sql": sql, "args": [_codificar(a) for a in args]}


# Una sesión HTTP por base y por proceso: reutiliza la conexión TLS entre consultas y entre
# requests de una misma instancia de Vercel (antes cada consulta pagaba un handshake, ~1 s).
_sesiones: dict[str, requests.Session] = {}


def sentencias(script: str) -> list[str]:
    """Separa un script SQL en sentencias (sin comentarios `--`). No admite `;` dentro de strings."""
    sin_comentarios = re.sub(r"--[^\n]*", "", script)
    return [s.strip() for s in sin_comentarios.split(";") if s.strip()]


class TursoConnection:
    """Subconjunto de la API de sqlite3.Connection que usa store.py."""

    def __init__(self, url: str, token: str, timeout: int = 20):
        base = re.sub(r"^libsql://", "https://", url.strip()).rstrip("/")
        self._endpoint = f"{base}/v2/pipeline"
        self._timeout = timeout
        if self._endpoint not in _sesiones:
            sesion = requests.Session()
            sesion.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
            _sesiones[self._endpoint] = sesion
        self._http = _sesiones[self._endpoint]

    def _enviar(self, pedidos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        r = self._http.post(self._endpoint, json={"requests": pedidos + [{"type": "close"}]}, timeout=self._timeout)
        r.raise_for_status()
        return r.json().get("results", [])[: len(pedidos)]

    def _pipeline(self, sentencias: list[tuple[str, Sequence[Any]]]) -> list[_Cursor]:
        cursores: list[_Cursor] = []
        for res in self._enviar([{"type": "execute", "stmt": _stmt(sql, args)} for sql, args in sentencias]):
            if res.get("type") == "error":
                raise RuntimeError(f"Turso: {res.get('error', {}).get('message', res)}")
            cursores.append(_cursor(res["response"]["result"]))
        return cursores

    def batch(self, sentencias: list[tuple[str, Sequence[Any]]]) -> list[_Cursor]:
        """Varias consultas en un solo viaje HTTP (no atómico)."""
        return self._pipeline(sentencias) if sentencias else []

    def transaccion(self, sentencias: list[tuple[str, Sequence[Any]]]) -> list[_Cursor]:
        """Todo o nada, en un solo viaje: batch de Hrana con BEGIN, cada paso condicionado a que
        el anterior haya salido bien, COMMIT y ROLLBACK si algo falló."""
        if not sentencias:
            return []
        pasos: list[dict[str, Any]] = [{"stmt": {"sql": "BEGIN"}}]
        for sql, args in sentencias:
            pasos.append({"stmt": _stmt(sql, args), "condition": {"type": "ok", "step": len(pasos) - 1}})
        commit = len(pasos)
        pasos.append({"stmt": {"sql": "COMMIT"}, "condition": {"type": "ok", "step": commit - 1}})
        pasos.append({"stmt": {"sql": "ROLLBACK"}, "condition": {"type": "not", "cond": {"type": "ok", "step": commit}}})
        res = self._enviar([{"type": "batch", "batch": {"steps": pasos}}])[0]
        if res.get("type") == "error":
            raise RuntimeError(f"Turso: {res.get('error', {}).get('message', res)}")
        resultado = res["response"]["result"]
        for error in resultado.get("step_errors", [])[1:commit]:
            if error:
                raise RuntimeError(f"Turso: {error.get('message', error)}")
        if resultado.get("step_errors", [None] * (commit + 1))[commit]:
            raise RuntimeError("Turso: falló el COMMIT")
        return [_cursor(r) if r else _Cursor([]) for r in resultado.get("step_results", [])[1:commit]]

    def execute(self, sql: str, params: Sequence[Any] = ()) -> _Cursor:
        return self._pipeline([(sql, params)])[0]

    def executemany(self, sql: str, filas: Sequence[Sequence[Any]]) -> None:
        for i in range(0, len(filas), _LOTE):
            self._pipeline([(sql, f) for f in filas[i : i + _LOTE]])

    def executescript(self, script: str) -> None:
        todas = [(s, ()) for s in sentencias(script)]
        for i in range(0, len(todas), _LOTE):
            self._pipeline(todas[i : i + _LOTE])

    def commit(self) -> None:  # cada request se confirma solo
        pass

    def close(self) -> None:
        pass


def batch(conn: Any, sentencias: list[tuple[str, Sequence[Any]]]) -> list[Any]:
    """Varias consultas de lectura de una: un viaje en Turso, secuencial en SQLite."""
    if hasattr(conn, "batch"):
        return conn.batch(sentencias)
    return [conn.execute(sql, args) for sql, args in sentencias]


def transaccion(conn: Any, sentencias: list[tuple[str, Sequence[Any]]]) -> list[Any]:
    """Escrituras todo o nada. En Turso viaja en un solo request."""
    if hasattr(conn, "transaccion"):
        return conn.transaccion(sentencias)
    cursores = []
    conn.execute("BEGIN")
    try:
        for sql, args in sentencias:
            cursores.append(_Cursor(conn.execute(sql, args).fetchall()))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return cursores


def remoto_configurado() -> bool:
    return bool(os.environ.get("TURSO_DATABASE_URL") and os.environ.get("TURSO_AUTH_TOKEN"))


def connect(db_path: str | Path):
    if remoto_configurado():
        return TursoConnection(os.environ["TURSO_DATABASE_URL"], os.environ["TURSO_AUTH_TOKEN"])
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None: las transacciones se manejan a mano (ver `transaccion`).
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn
