"""Envío de alertas a Discord vía webhook."""
from __future__ import annotations

import logging
import os
import time

import requests

from .models import Ticket

log = logging.getLogger("radar.notify")

COLORS = {"alto": 0x2ECC71, "medio": 0xF1C40F, "bajo": 0x95A5A6, "error": 0xE74C3C}


def _color(score: int) -> int:
    if score >= 75:
        return COLORS["alto"]
    if score >= 60:
        return COLORS["medio"]
    return COLORS["bajo"]


def _trim(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def post(webhook: str, payload: dict) -> bool:
    if not webhook:
        log.warning("webhook vacío, no se envía nada")
        return False
    for intento in range(3):
        try:
            r = requests.post(webhook, json=payload, timeout=20)
            if r.status_code == 429:
                espera = float(r.json().get("retry_after", 2))
                time.sleep(espera + 0.5)
                continue
            r.raise_for_status()
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("discord intento %d falló: %s", intento + 1, exc)
            time.sleep(2 * (intento + 1))
    return False


def send_ticket(webhook: str, ticket: Ticket) -> bool:
    """Alerta rica: el ticket arriba, la propuesta lista para copiar abajo."""
    budget = f"USD {ticket.budget_usd}" if ticket.budget_usd else "no publicado"
    embed = {
        "title": _trim(ticket.title, 250),
        "url": ticket.url,
        "color": _color(ticket.score),
        "description": _trim(ticket.description, 600),
        "fields": [
            {"name": "Score", "value": f"**{ticket.score}**/100", "inline": True},
            {"name": "Módulo", "value": ticket.module or "—", "inline": True},
            {"name": "Presupuesto", "value": budget, "inline": True},
            {"name": "Fuente", "value": ticket.source, "inline": True},
            {"name": "Motor del pitch", "value": ticket.pitch_engine or "—", "inline": True},
            {
                "name": "Match",
                "value": _trim(", ".join(ticket.matched_keywords) or "—", 100),
                "inline": True,
            },
        ],
        "footer": {"text": f"radar-freelance · {ticket.fingerprint[:8]}"},
    }
    # El texto del aviso viene de terceros: nunca debe poder mencionar @everyone ni roles.
    sin_menciones = {"parse": []}
    payload = {"username": "Radar", "embeds": [embed], "allowed_mentions": sin_menciones}
    ok = post(webhook, payload)
    if not ok:
        return False

    # La propuesta va en un mensaje aparte, en bloque de código: se copia de un toque.
    crm = os.environ.get("JOBLY_URL", "").strip().rstrip("/")
    enlace_crm = f"\n📲 Abrir en Jobly: {crm}/ticket/{ticket.fingerprint}" if crm else ""
    pitch_msg = {
        "username": "Radar",
        "content": f"**PROPUESTA LISTA** · {_trim(ticket.title, 80)}\n"
        f"```\n{_trim(ticket.pitch, 1600)}\n```\n"
        f"🔗 {ticket.url}{enlace_crm}",
        "allowed_mentions": sin_menciones,
    }
    return post(webhook, pitch_msg)


def send_summary(webhook: str, revisados: int, nuevos: int, enviados: int, errores: list[str]) -> bool:
    desc = (
        f"Revisados: **{revisados}** · Nuevos: **{nuevos}** · Alertas: **{enviados}**"
    )
    if errores:
        desc += "\n\n**Fuentes con error:**\n" + "\n".join(f"• {e[:150]}" for e in errores[:6])
    return post(
        webhook,
        {
            "username": "Radar",
            "embeds": [
                {
                    "title": "Corrida del radar",
                    "description": desc,
                    "color": COLORS["error"] if errores else COLORS["bajo"],
                }
            ],
        },
    )
