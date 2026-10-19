"""Normalización para deduplicar y para leer números/fechas que vienen de planillas."""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from urllib.parse import urlsplit

# Parámetros de tracking que no cambian el aviso.
_TRACKING = re.compile(r"^(utm_|ref$|ref_|source$|fbclid$|gclid$|trk$|referrer$)", re.I)


def slug(texto: str | None) -> str:
    """'Acme S.A. — Data Analyst (Remote)' -> 'acme sa data analyst remote'."""
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def url_norm(url: str | None) -> str:
    """Misma oferta = misma URL normalizada: sin esquema, sin www, sin fragmento, sin tracking,
    sin barra final, en minúsculas el host. Los parámetros que identifican el aviso se conservan."""
    u = str(url or "").strip()
    if not u:
        return ""
    try:
        partes = urlsplit(u)
    except ValueError:
        return u.lower()
    host = (partes.hostname or "").lower().removeprefix("www.")
    query = "&".join(
        sorted(q for q in partes.query.split("&") if q and not _TRACKING.match(q.split("=", 1)[0]))
    )
    ruta = partes.path.rstrip("/")
    return f"{host}{ruta}" + (f"?{query}" if query else "")


def clave(empresa: str | None, titulo: str | None) -> str:
    """Empresa + título normalizados. Vacío si falta la empresa (sin empresa no es una clave fiable)."""
    e, t = slug(empresa), slug(titulo)
    return f"{e}|{t}" if e and t else ""


def entero(valor: object) -> int | None:
    """'1.500' / '1,500' / 'USD 1500' / '20 to 50' -> 1500 / 1500 / 1500 / 20."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return int(valor)
    m = re.search(r"\d[\d.,]*", str(valor))
    if not m:
        return None
    crudo = m.group(0).rstrip(".,")
    # "1.500" o "1,500" (miles) -> 1500; "12.5" -> 12
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", crudo):
        return int(re.sub(r"[.,]", "", crudo))
    try:
        return int(float(crudo.replace(",", ".")))
    except ValueError:
        return None


def decimal(valor: object) -> float | None:
    if valor is None or str(valor).strip() == "":
        return None
    m = re.search(r"\d+(?:[.,]\d+)?", str(valor))
    return float(m.group(0).replace(",", ".")) if m else None


def fecha_iso(valor: object) -> str:
    """AAAA-MM-DD válida o ''. Acepta también DD/MM/AAAA."""
    t = str(valor or "").strip()[:10]
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t) or None
    if not m:
        m2 = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
        if not m2:
            return ""
        d, mes, a = m2.groups()
        t = f"{a}-{int(mes):02d}-{int(d):02d}"
    try:
        return date.fromisoformat(t).isoformat()
    except ValueError:
        return ""


def si_no(valor: object) -> int | None:
    t = slug(str(valor or ""))
    if t in ("si", "yes", "true", "1", "verificado", "verified", "x"):
        return 1
    if t in ("no", "false", "0"):
        return 0
    return None


def celda(valor: object, largo: int = 4000) -> str:
    """Texto de una celda: recortado y sin el apóstrofo que neutraliza fórmulas (='…)."""
    t = str(valor if valor is not None else "").strip()
    if len(t) > 1 and t[0] == "'" and t[1] in "=+-@":
        t = t[1:]
    return t[:largo]


def celda_export(valor: object) -> str:
    """Neutraliza CSV injection al exportar: una celda que empieza con = + - @ tab o CR
    se prefija con apóstrofo para que Excel/Sheets no la evalúe como fórmula."""
    t = "" if valor is None else str(valor)
    return "'" + t if t[:1] in ("=", "+", "-", "@", "\t", "\r") else t
