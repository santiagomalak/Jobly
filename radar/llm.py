"""Cascada de LLMs: gratis primero, siempre con red de seguridad.

Orden de intento (el primero que responda gana):
  1. Groq            — free tier generoso y rapidísimo (gpt-oss-120b)
  2. OpenRouter free — modelos con sufijo :free, sin costo
  3. Ollama local    — corre en tu PC, sin internet ni límite
  4. Plantilla       — pitch armado con reglas, sin IA. NUNCA falla.

El nivel 4 es lo que hace que el sistema "funcione siempre": aunque se caigan
los cuatro proveedores, la alerta llega a Discord con una propuesta usable,
y vos la refinás en #03-copiloto-chat con Claude.
"""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

import requests

log = logging.getLogger("radar.llm")

TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "45"))


class LLMResult:
    def __init__(self, text: str, engine: str):
        self.text = text.strip()
        self.engine = engine


# --------------------------------------------------------------------------
def _groq(system: str, user: str) -> str | None:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None
    model = os.environ.get("GROQ_MODEL") or "openai/gpt-oss-120b"
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0.4,
            # gpt-oss es un modelo "razonador": gasta tokens en un campo interno
            # `reasoning` antes de escribir `content`. Con max_tokens chico el
            # presupuesto se lo come el razonamiento y content queda vacío.
            # reasoning_effort=low + margen de tokens evita eso.
            "max_tokens": 1200,
            "reasoning_effort": "low",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _openrouter(system: str, user: str) -> str | None:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        return None
    model = os.environ.get("OPENROUTER_MODEL") or "google/gemma-4-31b-it:free"
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://santiagomalak.is-a.dev",
            "X-Title": "radar-freelance",
        },
        json={
            "model": model,
            "temperature": 0.4,
            "max_tokens": 700,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _ollama(system: str, user: str) -> str | None:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "").strip()
    if not model:
        return None
    r = requests.post(
        f"{host}/api/chat",
        json={
            "model": model,
            "stream": False,
            "options": {"temperature": 0.4},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json().get("message", {}).get("content", "")


PROVIDERS = [("groq", _groq), ("openrouter", _openrouter), ("ollama", _ollama)]


def _call(name: str, fn, system: str, user: str) -> str | None:
    """Una llamada; ante 429 espera lo que pide el proveedor (tope 8 s) y reintenta una vez."""
    try:
        return fn(system, user)
    except requests.HTTPError as exc:
        resp = exc.response
        if resp is None or resp.status_code != 429:
            raise
        try:
            espera = min(float(resp.headers.get("retry-after", 3)), 8.0)
        except ValueError:
            espera = 3.0
        log.warning("%s pidió calma (429), reintento en %.0f s", name, espera)
        time.sleep(espera)
        return fn(system, user)


def generate(system: str, user: str, fallback: str, min_len: int = 80) -> LLMResult:
    """Intenta cada proveedor en orden. Si todos fallan, devuelve el fallback."""
    for name, fn in PROVIDERS:
        try:
            out = _call(name, fn, system, user)
            if out and len(out.strip()) >= min_len:
                return LLMResult(_sanitize(out), name)
            if out:
                log.warning("%s devolvió una respuesta demasiado corta", name)
        except Exception as exc:  # noqa: BLE001
            log.warning("%s falló: %s", name, exc)
    return LLMResult(fallback, "plantilla")


_BANNED = [
    r"^\s*(hi|hello|hey|hola|good (morning|afternoon))\b.*\n?",
    r"i am a passionate.*\n?",
    r"i hope this (message|email) finds you well.*\n?",
    r"^\s*(sure|claro|of course|here('| i)s (the|your)).*\n?",
]


def _sanitize(text: str) -> str:
    """Saca preámbulos del modelo y saludos genéricos prohibidos por la memoria."""
    out = text.strip()
    out = re.sub(r"^```[a-z]*\n|```$", "", out, flags=re.M).strip()
    for pattern in _BANNED:
        out = re.sub(pattern, "", out, flags=re.I | re.M)
    return out.strip()


def available() -> dict[str, bool]:
    return {
        "groq": bool(os.environ.get("GROQ_API_KEY", "").strip()),
        "openrouter": bool(os.environ.get("OPENROUTER_API_KEY", "").strip()),
        "ollama": bool(os.environ.get("OLLAMA_MODEL", "").strip()),
        "plantilla": True,
    }
