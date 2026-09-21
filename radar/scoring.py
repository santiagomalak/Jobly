"""Motor de evaluación: contrasta el ticket contra la memoria modular."""
from __future__ import annotations

import re
from typing import Any

from .models import Ticket

# Presupuestos en el texto: $300, USD 300, 300 usd, $250-$400, 25/hr
_MONEY = re.compile(
    r"(?:usd|us\$|\$)\s?(\d{2,6})(?:\s?[-–a]\s?(?:usd|us\$|\$)?\s?(\d{2,6}))?"
    r"|(\d{2,6})\s?(?:usd|dolares|dólares)",
    re.I,
)
_HOURLY = re.compile(r"(\d{1,3})\s?(?:usd|\$)?\s?/\s?(?:hr|hour|h|hora)", re.I)


def extract_budget(text: str) -> int | None:
    """Devuelve el presupuesto estimado en USD, o None si no se puede inferir.

    En rangos toma el extremo bajo (pesimismo deliberado: mejor descartar de más).
    En tarifas por hora estima 12 h de trabajo.
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
            value = int(low)
        except ValueError:
            continue
        if not 20 <= value <= 100_000:
            continue
        best = value if best is None else min(best, value)
    return best


def _hits(text: str, words: list[str], cap: int = 3) -> list[str]:
    found = [w for w in words if w in text]
    return found[:cap]


def score_ticket(ticket: Ticket, taxonomy: dict[str, Any], cfg: dict[str, Any]) -> Ticket:
    text = ticket.text
    reasons: list[str] = []

    # 1. Killers — descarte inmediato
    for killer in taxonomy.get("killers", []):
        if str(killer).lower() in text:
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
        if str(word).lower() in text:
            score += int(pts)
            reasons.append(f"bonus '{word}': +{pts}")
    for word, pts in taxonomy.get("penalizaciones", {}).items():
        if str(word).lower() in text:
            score += int(pts)
            reasons.append(f"penaliza '{word}': {pts}")

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
    else:
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
