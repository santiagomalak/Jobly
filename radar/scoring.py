"""Motor de evaluación: contrasta el ticket contra la memoria modular."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from .models import Ticket

# Presupuestos en el texto: $300, USD 300, 300 usd, $250-$400, $1,500, $90k, 25/hr
_NUM = r"\d{1,3}(?:[.,]\d{3})+|\d{2,6}"
_MONEY = re.compile(
    rf"(?:usd|us\$|\$)\s?({_NUM})(k)?(?:\s?[-–a]\s?(?:usd|us\$|\$)?\s?(?:{_NUM})k?)?"
    rf"|({_NUM})\s?(?:usd|dolares|dólares)",
    re.I,
)
_HOURLY = re.compile(r"(\d{1,3})\s?(?:usd|\$)?\s?/\s?(?:hr|hour|h|hora)", re.I)

# Regiones que incluyen a Santiago (Argentina, UTC-3). Solo se evalúa si la fuente informa ubicación.
_REGION_OK = re.compile(
    r"worldwide|anywhere|everywhere|global|any location|latam|latin|south america|americas|argentina",
    re.I,
)

_NIVEL_ALTO = {"senior", "manager", "director", "executive", "lead", "staff", "principal"}
_NIVEL_BAJO = {"entry-level", "entry level", "junior", "intern"}

# Un ticket de 1-3 días no vale más que esto. Por encima es un sueldo anual, no un proyecto.
_TOPE_PROYECTO_USD = 20_000


def extract_budget(text: str) -> int | None:
    """Devuelve el presupuesto estimado en USD, o None si no se puede inferir.

    En rangos toma el extremo bajo (pesimismo deliberado: mejor descartar de más).
    En tarifas por hora estima 12 h de trabajo. Cifras de sueldo anual (> tope) se ignoran.
    """
    hourly = _HOURLY.search(text)
    if hourly:
        try:
            return int(hourly.group(1)) * 12
        except ValueError:
            pass

    best: int | None = None
    for m in _MONEY.finditer(text):
        low = m.group(1) or m.group(3)
        if not low:
            continue
        try:
            value = int(re.sub(r"[.,]", "", low)) * (1000 if m.group(2) else 1)
        except ValueError:
            continue
        if not 20 <= value <= _TOPE_PROYECTO_USD:
            continue
        best = value if best is None else min(best, value)
    return best


@lru_cache(maxsize=None)
def _patron(kw: str, exacta: bool) -> re.Pattern[str]:
    """Keyword con límites de palabra. La búsqueda por subcadena hacía que "$5" matara "$500",
    "rag" pegara en "average" y "bot" en "both".

    Inicio siempre en límite. Final: exacta (killers) = sin letra/dígito después ni decimales;
    si no, las keywords cortas (<= 4) son palabra completa (con plural) y las largas admiten
    sufijos ("automat" -> "automation", "scraper" -> "scrapers").
    """
    base = re.escape(kw.lower().strip())
    if exacta:
        fin = r"(?![a-z0-9]|[.,]\d)"
    else:
        fin = r"s?(?![a-z0-9])" if len(kw.strip()) <= 4 else ""
    return re.compile(r"(?<![a-z0-9])" + base + fin)


def es_oferta_de_empleo(ticket: Ticket) -> bool:
    """Puesto de una bolsa de empleo (Himalayas, Remotive, Jobicy...), no un proyecto con presupuesto.
    Lo marca la fuente con una etiqueta `tipo:`. Se postula con carta, no con plan de 1-3 días."""
    return any(t.startswith("tipo:") for t in ticket.tags)


def _hits(text: str, words: list[str], cap: int = 3) -> list[str]:
    found = [w for w in words if _patron(w, False).search(text)]
    return found[:cap]


def score_ticket(ticket: Ticket, taxonomy: dict[str, Any], cfg: dict[str, Any]) -> Ticket:
    text = ticket.text
    reasons: list[str] = []

    # 1. Killers — descarte inmediato
    for killer in taxonomy.get("killers", []):
        if _patron(str(killer), True).search(text):
            ticket.verdict = "discard"
            ticket.reasons = [f"killer: '{killer}'"]
            ticket.score = 0
            return ticket

    # 2. Módulo ganador
    best_module, best_points, best_kws = "", 0, []
    for module, words in taxonomy.get("modulos", {}).items():
        strong = _hits(text, [w.lower() for w in words.get("strong", [])])
        weak = _hits(text, [w.lower() for w in words.get("weak", [])])
        points = len(strong) * 12 + len(weak) * 4
        if points > best_points:
            best_module, best_points, best_kws = module, points, strong + weak

    if not best_module:
        ticket.verdict = "discard"
        ticket.reasons = ["ningún módulo hizo match"]
        return ticket

    ticket.module = best_module
    ticket.matched_keywords = best_kws
    score = best_points
    reasons.append(f"módulo {best_module}: +{best_points} ({', '.join(best_kws)})")

    # 3. Bonus y penalizaciones transversales
    for word, pts in taxonomy.get("bonus", {}).items():
        if _patron(str(word), False).search(text):
            score += int(pts)
            reasons.append(f"bonus '{word}': +{pts}")
    for word, pts in taxonomy.get("penalizaciones", {}).items():
        if _patron(str(word), False).search(text):
            score += int(pts)
            reasons.append(f"penaliza '{word}': {pts}")

    # 3b. Elegibilidad, tipo de contrato y seniority (etiquetas de las fuentes estructuradas)
    seniority_aplicado = False
    for tag in ticket.tags:
        if tag.startswith("seniority:") and not seniority_aplicado:
            nivel = tag.split(":", 1)[1].strip().lower()
            if nivel in _NIVEL_ALTO:
                score -= 10
                reasons.append(f"seniority {nivel}: -10")
                seniority_aplicado = True
            elif nivel in _NIVEL_BAJO:
                score += 4
                reasons.append(f"seniority {nivel}: +4")
                seniority_aplicado = True
            continue
        if tag.startswith("ubicacion:"):
            lugar = tag.split(":", 1)[1].strip()
            if lugar and not _REGION_OK.search(lugar):
                score -= 30
                reasons.append(f"ubicación requerida sin Argentina/LATAM ({lugar[:40]}): -30")
        elif tag in ("tipo:contract", "tipo:freelance"):
            score += 6
            reasons.append("tipo contrato/freelance: +6")

    # 4. Presupuesto
    budget = extract_budget(f"{ticket.raw_budget} {ticket.title} {ticket.description}")
    ticket.budget_usd = budget
    floor = int(cfg.get("min_budget_usd", 120))
    if budget is not None:
        if budget < floor:
            ticket.verdict = "discard"
            ticket.reasons = reasons + [f"presupuesto ${budget} < piso ${floor}"]
            ticket.score = max(score, 0)
            return ticket
        if budget >= 300:
            score += 14
            reasons.append(f"presupuesto ${budget}: +14")
        elif budget >= 180:
            score += 8
            reasons.append(f"presupuesto ${budget}: +8")
        else:
            score += 3
            reasons.append(f"presupuesto ${budget}: +3")
    elif not es_oferta_de_empleo(ticket):
        score -= 4
        reasons.append("sin presupuesto visible: -4")

    # 5. Frescura: un ticket viejo ya tiene 40 propuestas
    if ticket.published:
        reasons.append(f"publicado: {ticket.published}")

    # 6. Descripción demasiado corta = alcance indefinido
    if len(ticket.description) < 100:
        score -= 4
        reasons.append("descripción muy corta: -4")

    ticket.score = max(0, min(100, score))
    ticket.reasons = reasons
    ticket.verdict = "pass" if ticket.score >= int(cfg.get("min_score", 55)) else "discard"
    if ticket.verdict == "discard":
        ticket.reasons.append(f"score {ticket.score} < mínimo {cfg.get('min_score')}")
    return ticket
