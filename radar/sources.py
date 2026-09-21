"""Fuentes de tickets: RSS, JSON APIs y scraping ligero.

Todas devuelven list[Ticket]. Una fuente que falla NO tumba la corrida:
se loguea y se sigue con las demás.
"""
from __future__ import annotations

import html
import logging
import re
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
        tags = [str(t) for t in job.get("tags", [])]
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
# Reddit (JSON público, sin credenciales)
# --------------------------------------------------------------------------
def fetch_reddit(name: str, url: str, cfg: dict[str, Any]) -> list[Ticket]:
    r = requests.get(
        url,
        headers={"User-Agent": cfg.get("user_agent")},
        timeout=int(cfg.get("http_timeout", 20)),
    )
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
        params={"tags": "comment", "query": '"seeking freelancer"'},
        timeout=int(cfg.get("http_timeout", 20)),
    )
    r.raise_for_status()
    tickets: list[Ticket] = []
    for hit in r.json().get("hits", [])[:60]:
        body = _clean(hit.get("comment_text", ""))
        if len(body) < 120:
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


FETCHERS: dict[str, Callable[..., list[Ticket]]] = {
    "rss": fetch_rss,
    "remoteok": fetch_remoteok,
    "reddit": fetch_reddit,
    "hn": fetch_hn_freelance,
}


def collect(sources: list[dict[str, Any]], cfg: dict[str, Any]) -> tuple[list[Ticket], list[str]]:
    """Recorre todas las fuentes habilitadas. Devuelve (tickets, errores)."""
    all_tickets: list[Ticket] = []
    errors: list[str] = []
    for src in sources:
        if not src.get("enabled", True):
            continue
        kind = src.get("type", "rss")
        fetcher = FETCHERS.get(kind)
        if not fetcher:
            errors.append(f"{src.get('name')}: tipo desconocido '{kind}'")
            continue
        try:
            found = fetcher(src["name"], src.get("url", ""), cfg)
            log.info("%s: %d tickets", src["name"], len(found))
            all_tickets.extend(found)
        except Exception as exc:  # noqa: BLE001 - una fuente caída no frena el radar
            msg = f"{src.get('name')}: {type(exc).__name__}: {exc}"
            log.warning(msg)
            errors.append(msg)
    return all_tickets, errors
