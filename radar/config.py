"""Carga de configuración y variables de entorno."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DEFAULTS: dict[str, Any] = {
    "min_score": 55,
    "min_budget_usd": 120,
    "max_tickets_per_run": 12,
    "memory_dir": "memoria",
    "db_path": "data/radar.sqlite",
    "lookback_hours": 36,
    "http_timeout": 20,
    "user_agent": "radar-freelance/1.0 (+https://santiagomalak.is-a.dev)",
}


def load_config() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    path = ROOT / "config.yaml"
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        cfg.update(loaded)
    cfg["root"] = ROOT
    return cfg


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def discord_webhook(channel: str) -> str:
    """channel: 'radar' | 'propuestas' | 'errores'"""
    return env(f"DISCORD_WEBHOOK_{channel.upper()}")
