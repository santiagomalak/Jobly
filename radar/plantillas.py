"""Biblioteca de propuestas: plantillas reutilizables con su tasa de respuesta real.

Cada envío guarda qué plantilla se usó (tickets.plantilla_id), así se ve cuál consigue
respuestas y cuál conviene dejar de usar. Variables que se rellenan solas:
{titulo} {empresa} {fuente} {stack} {presupuesto}. Lo que va entre <...> se completa a mano.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import db
from . import etapas as et

TIPOS = ("freelance", "empleo", "seguimiento")
IDIOMAS = ("es", "en", "pt")
VARIABLES = ("titulo", "empresa", "fuente", "stack", "presupuesto")
_PENDIENTE = re.compile(r"<[^<>\n]{1,60}>|\[COMPLETAR[^\]]*\]")
_MIN_ENVIOS = 5  # debajo de esto la tasa no dice nada todavía


def _ahora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _en(valores: tuple[str, ...]) -> str:
    return ",".join(f"'{v}'" for v in valores)


_STATS = f"""
    SUM(CASE WHEN t.postulado_at IS NOT NULL THEN 1 ELSE 0 END) AS envios,
    SUM(CASE WHEN t.etapa IN ({_en(et.RESPONDIDAS)}) THEN 1 ELSE 0 END) AS respuestas,
    SUM(CASE WHEN t.etapa = 'ganada' THEN 1 ELSE 0 END) AS ganadas"""


def _con_tasa(d: dict[str, Any]) -> dict[str, Any]:
    envios = int(d.get("envios") or 0)
    d["envios"], d["respuestas"], d["ganadas"] = envios, int(d.get("respuestas") or 0), int(d.get("ganadas") or 0)
    d["tasa"] = round(100 * d["respuestas"] / envios) if envios else None
    d["confiable"] = envios >= _MIN_ENVIOS
    return d


def listar(conn: Any, tipo: str | None = None) -> list[dict[str, Any]]:
    """Plantillas con envíos, respuestas y ganadas. Las que mejor responden primero."""
    filtro, params = ("WHERE p.tipo = ?", (tipo,)) if tipo else ("", ())
    rows = conn.execute(
        f"""SELECT p.id, p.nombre, p.tipo, p.idioma, p.cuerpo, p.updated_at, {_STATS}
            FROM plantillas p LEFT JOIN tickets t ON t.plantilla_id = p.id
            {filtro} GROUP BY p.id""",
        params,
    ).fetchall()
    out = [_con_tasa(dict(r)) for r in rows]
    out.sort(key=lambda p: (-(p["tasa"] if p["confiable"] else -1), -p["envios"], p["nombre"].lower()))
    return out


def sin_plantilla(conn: Any) -> dict[str, Any]:
    """Línea de base: envíos hechos sin plantilla (pitch de IA o texto a mano)."""
    r = conn.execute(f"SELECT {_STATS} FROM tickets t WHERE t.plantilla_id IS NULL").fetchone()
    return _con_tasa(dict(r) if r else {})


def obtener(conn: Any, pid: int) -> dict[str, Any] | None:
    r = conn.execute("SELECT * FROM plantillas WHERE id = ?", (pid,)).fetchone()
    return dict(r) if r else None


def validar(nombre: str, tipo: str, idioma: str, cuerpo: str) -> str | None:
    if not nombre.strip() or len(nombre) > 80:
        return "El nombre es obligatorio (hasta 80 caracteres)"
    if tipo not in TIPOS:
        return "Tipo inválido"
    if idioma not in IDIOMAS:
        return "Idioma inválido"
    if not cuerpo.strip() or len(cuerpo) > 6000:
        return "El texto es obligatorio (hasta 6000 caracteres)"
    return None


def guardar(conn: Any, nombre: str, tipo: str, idioma: str, cuerpo: str, pid: int | None = None) -> int:
    error = validar(nombre, tipo, idioma, cuerpo)
    if error:
        raise ValueError(error)
    ahora = _ahora()
    if pid:
        conn.execute(
            "UPDATE plantillas SET nombre = ?, tipo = ?, idioma = ?, cuerpo = ?, updated_at = ? WHERE id = ?",
            (nombre.strip(), tipo, idioma, cuerpo.strip(), ahora, pid),
        )
        conn.commit()
        return pid
    cur = conn.execute(
        "INSERT INTO plantillas (nombre, tipo, idioma, cuerpo, created_at, updated_at) VALUES (?,?,?,?,?,?)",
        (nombre.strip(), tipo, idioma, cuerpo.strip(), ahora, ahora),
    )
    conn.commit()
    return int(cur.lastrowid)


def borrar(conn: Any, pid: int) -> None:
    """Borra la plantilla; los envíos que la usaron quedan como 'sin plantilla'."""
    db.transaccion(conn, [
        ("UPDATE tickets SET plantilla_id = NULL WHERE plantilla_id = ?", (pid,)),
        ("DELETE FROM plantillas WHERE id = ?", (pid,)),
    ])


def asignar(conn: Any, fingerprint: str, pid: int | None) -> None:
    conn.execute("UPDATE tickets SET plantilla_id = ? WHERE fingerprint = ?", (pid, fingerprint))
    conn.commit()


def valores(row: Any) -> dict[str, str]:
    """Datos del ticket para rellenar las variables."""
    try:
        datos = json.loads(row["payload"] or "{}")
    except ValueError:
        datos = {}
    extra = datos.get("extra") or {}
    empresa = str(extra.get("empresa") or "")
    if not empresa:
        empresa = next((str(t).split(":", 1)[1] for t in datos.get("tags", []) if str(t).startswith("empresa:")), "")
    stack = ", ".join((datos.get("matched_keywords") or [])[:4])
    pmin, pmax = row["presupuesto_min"], row["presupuesto_max"]
    moneda = row["moneda"] or "USD"
    if pmin and pmax and pmin != pmax:
        presupuesto = f"{moneda} {pmin}–{pmax}"
    elif pmin or pmax:
        presupuesto = f"{moneda} {pmin or pmax}"
    elif row["budget_usd"]:
        presupuesto = f"USD {row['budget_usd']}"
    else:
        presupuesto = ""
    return {"titulo": row["title"] or "", "empresa": empresa, "fuente": row["source"] or "",
            "stack": stack, "presupuesto": presupuesto}


def rellenar(cuerpo: str, vals: dict[str, str]) -> str:
    """Reemplaza {variable}. Si falta el dato, deja <variable> para completarlo a mano."""
    def _sub(m: re.Match) -> str:
        clave = m.group(1)
        return vals.get(clave) or f"<{clave}>"
    return re.sub(r"\{(" + "|".join(VARIABLES) + r")\}", _sub, cuerpo)


def pendientes(texto: str) -> list[str]:
    """Huecos sin completar (<...> o [COMPLETAR]) para avisar antes de copiar."""
    return _PENDIENTE.findall(texto or "")


# ---------- plantillas base desde memoria/06_plantillas_venta.md ----------
_IDIOMA = {"ES": "es", "EN": "en", "PT": "pt"}
_ROTULO = re.compile(r"^\[[A-ZÁÉÍÓÚ]+\]:\s*", re.M)


def _bloques(texto: str) -> list[tuple[str, str]]:
    """[(encabezado ##/###, primer bloque ``` debajo)]."""
    out, titulo, dentro, buf = [], None, False, []
    for linea in texto.splitlines():
        if linea.startswith("```"):
            if dentro:
                if titulo:
                    out.append((titulo, "\n".join(buf)))
                    titulo = None
                dentro, buf = False, []
            else:
                dentro = True
        elif dentro:
            buf.append(linea)
        elif linea.startswith(("## ", "### ")):
            titulo = linea.lstrip("#").strip()
    return out


def desde_memoria(memoria_dir: Path) -> list[dict[str, str]]:
    archivo = Path(memoria_dir) / "06_plantillas_venta.md"
    if not archivo.exists():
        return []
    out = []
    for titulo, cuerpo in _bloques(archivo.read_text(encoding="utf-8")):
        if titulo.upper().startswith("SEGUIMIENTO"):
            nombre, tipo, idioma = titulo.split("—")[0].strip().capitalize(), "seguimiento", "es"
        elif titulo.startswith("Versión"):
            cod = titulo.split()[1].split("-")[0].upper()
            nombre, tipo, idioma = f"Maestra freelance {cod}", "freelance", _IDIOMA.get(cod, "es")
        else:
            continue
        cuerpo = _ROTULO.sub("", cuerpo)  # [PLAN]: y similares son guía interna, no van al cliente
        out.append({"nombre": nombre, "tipo": tipo, "idioma": idioma, "cuerpo": cuerpo.strip()})
    return out


def cargar_base(conn: Any, memoria_dir: Path) -> int:
    """Carga las plantillas de memoria/06 que todavía no existen (por nombre). Devuelve cuántas."""
    existentes = {r["nombre"] for r in conn.execute("SELECT nombre FROM plantillas").fetchall()}
    nuevas = [p for p in desde_memoria(memoria_dir) if p["nombre"] not in existentes]
    for p in nuevas:
        guardar(conn, p["nombre"], p["tipo"], p["idioma"], p["cuerpo"])
    return len(nuevas)
