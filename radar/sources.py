"""Fuentes de tickets: RSS, JSON APIs y scraping ligero.

Todas devuelven list[Ticket]. Una fuente que falla NO tumba la corrida:
se loguea y se sigue con las demás.
"""
from __future__ import annotations

import csv
import html
import io
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import feedparser
import requests

from .models import Ticket

log = logging.getLogger("radar.sources")


def _clean(raw: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", raw or "")
    txt = html.unescape(txt)
    return re.sub(r"\s+", " ", txt).strip()


def _is_fresh(entry: Any, hours: int) -> bool:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if not parsed:
        return True  # sin fecha, no descartamos
    dt = datetime(*parsed[:6], tzinfo=timezone.utc)
    return dt >= datetime.now(timezone.utc) - timedelta(hours=hours)


# --------------------------------------------------------------------------
# RSS genérico (Upwork, WeWorkRemotely, Reddit, lo que sea)
# --------------------------------------------------------------------------
def fetch_rss(name: str, url: str, cfg: dict[str, Any]) -> list[Ticket]:
    tickets: list[Ticket] = []
    feed = feedparser.parse(url, agent=cfg.get("user_agent"))
    if getattr(feed, "bozo", 0) and not feed.entries:
        raise RuntimeError(f"feed ilegible: {getattr(feed, 'bozo_exception', '')}")

    for entry in feed.entries:
        if not _is_fresh(entry, int(cfg.get("lookback_hours", 36))):
            continue
        desc = _clean(getattr(entry, "summary", "") or getattr(entry, "description", ""))
        budget = ""
        m = re.search(r"(Budget|Hourly Range|Fixed[- ]price)[:\s]*([^<\n]{0,60})", desc, re.I)
        if m:
            budget = m.group(0)
        tickets.append(
            Ticket(
                source=name,
                title=_clean(getattr(entry, "title", "")),
                url=getattr(entry, "link", ""),
                description=desc[:4000],
                published=getattr(entry, "published", ""),
                raw_budget=budget,
            )
        )
    return tickets


# --------------------------------------------------------------------------
# RemoteOK (API JSON pública)
# --------------------------------------------------------------------------
def fetch_remoteok(name: str, url: str, cfg: dict[str, Any]) -> list[Ticket]:
    r = requests.get(
        url or "https://remoteok.com/api",
        headers={"User-Agent": cfg.get("user_agent")},
        timeout=int(cfg.get("http_timeout", 20)),
    )
    r.raise_for_status()
    data = r.json()
    tickets: list[Ticket] = []
    for job in data:
        if not isinstance(job, dict) or "position" not in job:
            continue  # la primera fila es el disclaimer legal
        # salary_min/max es sueldo anual full-time, no presupuesto de proyecto.
        # No va en raw_budget: scoring.extract_budget lo leería como plata de un
        # ticket freelance y le daría bonus a ofertas de empleo full-time.
        tags = [str(t) for t in job.get("tags", [])] + ["tipo:empleo"]  # bolsa de empleo: se postula con carta
        if job.get("salary_min"):
            tags.append(f"salario_full_time:USD {job.get('salary_min')}-{job.get('salary_max')}")
        tickets.append(
            Ticket(
                source=name,
                title=_clean(job.get("position", "")),
                url=job.get("url") or job.get("apply_url", ""),
                description=_clean(job.get("description", ""))[:4000],
                published=job.get("date", ""),
                tags=tags,
            )
        )
    return tickets


# --------------------------------------------------------------------------
# Remotive (API pública). Uso personal permitido; NO republicar sus avisos a
# terceros ni usarlos para juntar leads externos (rompe sus ToS). Máx. ~4
# requests/día según piden ellos mismos — nuestro cron corre 2 veces/día, ok.
# --------------------------------------------------------------------------
def fetch_remotive(name: str, url: str, cfg: dict[str, Any]) -> list[Ticket]:
    r = requests.get(
        url or "https://remotive.com/api/remote-jobs",
        headers={"User-Agent": cfg.get("user_agent")},
        timeout=int(cfg.get("http_timeout", 20)),
    )
    r.raise_for_status()
    data = r.json()
    tickets: list[Ticket] = []
    for job in data.get("jobs", []):
        salary = (job.get("salary") or "").strip()
        tags = [str(t) for t in job.get("tags", [])]
        # Solo una tarifa por hora es un precio de trabajo; "$90k - $105k" es un sueldo anual
        # y en raw_budget se leería como presupuesto de proyecto.
        es_tarifa = bool(re.search(r"/\s?(hr|hour)|per hour|hourly", salary, re.I))
        if salary and not es_tarifa:
            tags.append(f"salario:{salary}")
        if job.get("job_type"):
            tags.append(f"tipo:{job['job_type']}")
        if job.get("candidate_required_location"):
            tags.append(f"ubicacion:{job['candidate_required_location']}")
        tickets.append(
            Ticket(
                source=name,
                title=_clean(job.get("title", "")),
                url=job.get("url", ""),
                description=_clean(job.get("description", ""))[:4000],
                published=job.get("publication_date", ""),
                raw_budget=salary if es_tarifa else "",
                tags=tags,
            )
        )
    return tickets


# --------------------------------------------------------------------------
# Himalayas (API pública, gratis y sin auth). Condiciones: link de atribución
# (el CRM lo muestra en el pie) y sin polling excesivo (429 si te pasás).
# Filtros útiles: q, worldwide=true, employment_type=contractor, country=AR.
# --------------------------------------------------------------------------
_TIPO = {
    "contractor": "contract", "contract": "contract", "freelance": "freelance",
    "full time": "full_time", "full-time": "full_time", "part time": "part_time", "part-time": "part_time",
}


def _tag_tipo(valor: str) -> str | None:
    t = _TIPO.get(str(valor).strip().lower())
    return f"tipo:{t}" if t else None


def _epoch_iso(valor: Any) -> str:
    try:
        return datetime.fromtimestamp(int(valor), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def _himalayas_ticket(name: str, job: dict[str, Any]) -> Ticket:
    tags = [t for t in [_tag_tipo(job.get("employmentType", ""))] if t]
    restricciones = job.get("locationRestrictions") or []
    tags.append("ubicacion:" + (", ".join(restricciones) if restricciones else "Worldwide"))  # vacío = mundial
    tags += [f"seniority:{s}" for s in job.get("seniority") or []]
    if job.get("minSalary"):
        tags.append(f"salario:{job['minSalary']}-{job.get('maxSalary')} {job.get('currency', '')} {job.get('salaryPeriod', '')}")
    return Ticket(
        source=name,
        title=_clean(job.get("title", "")),
        url=job.get("applicationLink") or job.get("guid", ""),
        description=_clean(job.get("description") or job.get("excerpt", ""))[:4000],
        published=_epoch_iso(job.get("pubDate")),
        tags=tags,
    )


def fetch_himalayas(name: str, url: str, cfg: dict[str, Any]) -> list[Ticket]:
    """Una consulta por cada `queries` de la fuente (sources.yaml), con `params` comunes."""
    src = cfg.get("_src", {})
    base = {k: str(v) for k, v in (src.get("params") or {}).items()}
    max_dias = int(src.get("max_age_days", 45))
    limite = datetime.now(timezone.utc) - timedelta(days=max_dias)
    queries = src.get("queries") or [""]
    vistos: dict[str, Ticket] = {}
    fallos = 0
    for q in queries:
        params = dict(base, **({"q": q} if q else {}))
        try:
            r = requests.get(
                url or "https://himalayas.app/jobs/api/search",
                params=params,
                headers={"User-Agent": cfg.get("user_agent")},
                timeout=int(cfg.get("http_timeout", 20)),
            )
            if r.status_code == 429:
                log.warning("%s: 429 (límite de Himalayas), corto acá", name)
                break
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
        except (requests.RequestException, ValueError) as exc:
            fallos += 1
            log.warning("%s: consulta %r falló: %s", name, q, exc)
            continue
        for job in jobs:
            clave = job.get("guid") or job.get("applicationLink")
            try:
                viejo = datetime.fromtimestamp(int(job.get("pubDate")), tz=timezone.utc) < limite
            except (TypeError, ValueError, OSError):
                viejo = False
            if clave and clave not in vistos and not viejo:
                vistos[clave] = _himalayas_ticket(name, job)
        time.sleep(0.3)
    if fallos == len(queries):
        raise RuntimeError("todas las consultas a Himalayas fallaron")
    return list(vistos.values())


# --------------------------------------------------------------------------
# Jobicy (API pública). Condición: crédito con link a Jobicy y que el botón de
# postular lleve a la URL original del aviso (el CRM lo hace: ticket.url).
# --------------------------------------------------------------------------
def fetch_jobicy(name: str, url: str, cfg: dict[str, Any]) -> list[Ticket]:
    src = cfg.get("_src", {})
    base = {k: str(v) for k, v in (src.get("params") or {}).items()}
    vistos: dict[str, Ticket] = {}
    consultas = src.get("queries") or [{}]
    fallos = 0
    for extra in consultas:
        params = dict(base, count="50", **{k: str(v) for k, v in dict(extra).items()})
        try:
            r = requests.get(
                url or "https://jobicy.com/api/v2/remote-jobs",
                params=params,
                headers={"User-Agent": cfg.get("user_agent")},
                timeout=int(cfg.get("http_timeout", 20)),
            )
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
        except (requests.RequestException, ValueError) as exc:
            fallos += 1
            log.warning("%s: consulta %r falló: %s", name, extra, exc)
            continue
        for job in jobs:
            tipos = job.get("jobType") if isinstance(job.get("jobType"), list) else [job.get("jobType")]
            tags = [t for t in (_tag_tipo(x) for x in tipos if x) if t]
            geo = re.sub(r"\s+", " ", str(job.get("jobGeo") or "")).strip()
            if geo:
                tags.append(f"ubicacion:{geo}")
            if job.get("jobLevel"):
                tags.append(f"seniority:{job['jobLevel']}")
            if job.get("salaryMin"):
                tags.append(f"salario:{job['salaryMin']}-{job.get('salaryMax')} {job.get('salaryCurrency', '')} {job.get('salaryPeriod', '')}")
            clave = job.get("url") or str(job.get("id"))
            if clave and clave not in vistos:
                vistos[clave] = Ticket(
                    source=name,
                    title=_clean(job.get("jobTitle", "")),
                    url=job.get("url", ""),
                    description=_clean(job.get("jobDescription") or job.get("jobExcerpt", ""))[:4000],
                    published=job.get("pubDate", ""),
                    tags=tags,
                )
        time.sleep(0.3)
    if fallos == len(consultas):
        raise RuntimeError("todas las consultas a Jobicy fallaron")
    return list(vistos.values())


# --------------------------------------------------------------------------
# Reddit (JSON público, sin credenciales)
# --------------------------------------------------------------------------
_reddit_token: dict[str, Any] = {"valor": "", "expira": 0.0}


def _token_reddit(user_agent: str, timeout: int) -> str:
    """Token de solo lectura (OAuth "script app", client_credentials). Vacío si no hay credenciales."""
    cid, secreto = os.environ.get("REDDIT_CLIENT_ID", "").strip(), os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    if not (cid and secreto):
        return ""
    if _reddit_token["valor"] and time.time() < _reddit_token["expira"] - 60:
        return _reddit_token["valor"]
    r = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(cid, secreto),
        data={"grant_type": "client_credentials"},
        headers={"User-Agent": user_agent},
        timeout=timeout,
    )
    r.raise_for_status()
    datos = r.json()
    if "access_token" not in datos:
        raise RuntimeError(f"Reddit no devolvió token: {datos.get('error', datos)}")
    _reddit_token.update(valor=datos["access_token"], expira=time.time() + int(datos.get("expires_in", 3600)))
    return _reddit_token["valor"]


def fetch_reddit(name: str, url: str, cfg: dict[str, Any]) -> list[Ticket]:
    """Con REDDIT_CLIENT_ID/SECRET usa la API oficial (OAuth). Sin ellas prueba el JSON público,
    que Reddit suele bloquear con 403: en ese caso la fuente falla sola sin tumbar la corrida."""
    ua = os.environ.get("REDDIT_USER_AGENT") or cfg.get("user_agent")
    timeout = int(cfg.get("http_timeout", 20))
    token = _token_reddit(ua, timeout)
    headers = {"User-Agent": ua}
    destino = url
    if token:
        headers["Authorization"] = f"bearer {token}"
        destino = url.replace("https://www.reddit.com", "https://oauth.reddit.com").replace(".json", "")
        destino += ("&" if "?" in destino else "?") + "raw_json=1"
    r = requests.get(destino, headers=headers, timeout=timeout)
    r.raise_for_status()
    children = r.json().get("data", {}).get("children", [])
    cutoff = datetime.now(timezone.utc) - timedelta(hours=int(cfg.get("lookback_hours", 36)))
    tickets: list[Ticket] = []
    for child in children:
        d = child.get("data", {})
        created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
        if created < cutoff:
            continue
        title = _clean(d.get("title", ""))
        # r/forhire: solo interesan los [HIRING]
        if "forhire" in url.lower() and "[hiring]" not in title.lower():
            continue
        tickets.append(
            Ticket(
                source=name,
                title=title,
                url="https://www.reddit.com" + d.get("permalink", ""),
                description=_clean(d.get("selftext", ""))[:4000],
                published=created.isoformat(),
                tags=[d.get("link_flair_text") or ""],
            )
        )
    return tickets


# --------------------------------------------------------------------------
# Hacker News "Freelancer? Seeking freelancer?" vía Algolia
# --------------------------------------------------------------------------
def fetch_hn_freelance(name: str, url: str, cfg: dict[str, Any]) -> list[Ticket]:
    # Comillas = frase exacta en Algolia. Sin comillas hace OR entre "seeking" y
    # "freelancer" y trae sobre todo autopromoción de freelancers ("SEEKING WORK...")
    # en vez de pedidos de clientes ("SEEKING FREELANCER...").
    search = "https://hn.algolia.com/api/v1/search_by_date"
    r = requests.get(
        search,
        params={"tags": "comment", "query": '"seeking freelancer"', "hitsPerPage": 100},
        timeout=int(cfg.get("http_timeout", 20)),
    )
    r.raise_for_status()
    limite = datetime.now(timezone.utc) - timedelta(days=int(cfg.get("hn_lookback_days", 35)))
    tickets: list[Ticket] = []
    for hit in r.json().get("hits", []):
        body = _clean(hit.get("comment_text", ""))
        if len(body) < 120:
            continue
        # La frase exacta también aparece en comentarios sueltos que hablan del hilo;
        # los avisos reales de clientes arrancan con "SEEKING FREELANCER |".
        if "seeking freelancer" not in body[:60].lower():
            continue
        try:
            creado = datetime.fromisoformat(hit.get("created_at", "").replace("Z", "+00:00"))
        except ValueError:
            creado = None
        if creado and creado < limite:
            continue
        tickets.append(
            Ticket(
                source=name,
                title=body[:90],
                url=f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                description=body[:4000],
                published=hit.get("created_at", ""),
            )
        )
    return tickets


# --------------------------------------------------------------------------
# Google Sheets / Excel exportado como CSV (carga manual de leads)
# --------------------------------------------------------------------------
_SHEET_COLUMNS = {
    "title": ("title", "titulo", "título", "puesto"),
    "url": ("url", "link", "enlace"),
    "description": ("description", "descripcion", "descripción", "detalle"),
    "budget": ("budget", "presupuesto", "pago", "salary"),
}


def _pick_column(headers: list[str], names: tuple[str, ...]) -> str | None:
    lowered = {h.lower().strip(): h for h in headers}
    for name in names:
        if name in lowered:
            return lowered[name]
    return None


def fetch_sheet(name: str, url: str, cfg: dict[str, Any]) -> list[Ticket]:
    """Lee un Google Sheet publicado como CSV (Archivo > Compartir > Publicar en la
    web > CSV, o un Excel exportado a CSV y hosteado en cualquier URL pública)."""
    r = requests.get(url, timeout=int(cfg.get("http_timeout", 20)))
    r.raise_for_status()
    return parse_sheet_csv(r.text, name)


def parse_sheet_csv(texto: str, name: str) -> list[Ticket]:
    """CSV -> tickets. Columnas en cualquier orden, español o inglés: title/titulo (opcional,
    se infiere de la descripción), url/link (obligatoria), description/descripcion,
    budget/presupuesto (opcional). No filtra por antigüedad: es carga manual."""
    texto = texto.lstrip("﻿")
    try:  # pegar celdas desde Sheets/Excel da TSV; un Excel en español exporta con ";"
        dialecto = csv.Sniffer().sniff(texto[:3000], delimiters=",;\t")
    except csv.Error:
        dialecto = csv.excel
    reader = csv.DictReader(io.StringIO(texto), dialect=dialecto)
    if not reader.fieldnames:
        raise RuntimeError("el CSV no tiene encabezados")

    col_title = _pick_column(reader.fieldnames, _SHEET_COLUMNS["title"])
    col_url = _pick_column(reader.fieldnames, _SHEET_COLUMNS["url"])
    col_desc = _pick_column(reader.fieldnames, _SHEET_COLUMNS["description"])
    col_budget = _pick_column(reader.fieldnames, _SHEET_COLUMNS["budget"])
    if not col_url:
        raise RuntimeError(f"el CSV necesita una columna url/link (encabezados: {reader.fieldnames})")

    tickets: list[Ticket] = []
    for row in reader:
        link = (row.get(col_url) or "").strip()
        if not link:
            continue
        desc = (row.get(col_desc) or "").strip() if col_desc else ""
        title = (row.get(col_title) or "").strip() if col_title else ""
        tickets.append(
            Ticket(
                source=name,
                title=title or desc[:90] or link,
                url=link,
                description=desc[:4000],
                raw_budget=(row.get(col_budget) or "").strip() if col_budget else "",
            )
        )
    return tickets


FETCHERS: dict[str, Callable[..., list[Ticket]]] = {
    "rss": fetch_rss,
    "remoteok": fetch_remoteok,
    "reddit": fetch_reddit,
    "hn": fetch_hn_freelance,
    "sheet": fetch_sheet,
    "remotive": fetch_remotive,
    "himalayas": fetch_himalayas,
    "jobicy": fetch_jobicy,
}


def _correr_fuente(src: dict[str, Any], cfg: dict[str, Any]) -> tuple[list[Ticket], str | None]:
    """Una fuente, aislada: devuelve (tickets, error). Nunca levanta."""
    kind = src.get("type", "rss")
    fetcher = FETCHERS.get(kind)
    if not fetcher:
        return [], f"{src.get('name')}: tipo desconocido '{kind}'"
    try:
        found = fetcher(src["name"], src.get("url", ""), {**cfg, "_src": src})
        log.info("%s: %d tickets", src["name"], len(found))
        return found, None
    except Exception as exc:  # noqa: BLE001 - una fuente caída no frena el radar
        msg = f"{src.get('name')}: {type(exc).__name__}: {exc}"
        log.warning(msg)
        return [], msg


def collect(sources: list[dict[str, Any]], cfg: dict[str, Any]) -> tuple[list[Ticket], list[str]]:
    """Recorre las fuentes habilitadas EN PARALELO (son independientes y varias tardan segundos
    por consulta). El orden del resultado sigue el de sources.yaml. Devuelve (tickets, errores)."""
    activas = [s for s in sources if s.get("enabled", True)]
    if not activas:
        return [], []
    with ThreadPoolExecutor(max_workers=min(int(cfg.get("max_workers", 6)), len(activas))) as pool:
        resultados = list(pool.map(lambda s: _correr_fuente(s, cfg), activas))
    all_tickets = [t for found, _ in resultados for t in found]
    errors = [err for _, err in resultados if err]
    return all_tickets, errors
