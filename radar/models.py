"""Estructuras de datos del radar."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Ticket:
    """Una oferta de proyecto detectada por el radar."""

    source: str
    title: str
    url: str
    description: str = ""
    published: str = ""
    raw_budget: str = ""
    tags: list[str] = field(default_factory=list)
    fetched_at: str = field(default_factory=_now)

    # Rellenado por el motor de scoring
    score: int = 0
    module: str = ""
    matched_keywords: list[str] = field(default_factory=list)
    budget_usd: int | None = None
    reasons: list[str] = field(default_factory=list)
    verdict: str = "pending"  # pass | discard | pending

    # Rellenado por el generador de pitch
    pitch: str = ""
    pitch_engine: str = ""

    @property
    def fingerprint(self) -> str:
        """Huella estable para deduplicar entre fuentes."""
        norm = re.sub(r"[^a-z0-9 ]", "", self.title.lower())
        norm = re.sub(r"\s+", " ", norm).strip()
        base = f"{norm}|{self.url.split('?')[0]}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]

    @property
    def text(self) -> str:
        return f"{self.title}\n{self.description}".lower()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["fingerprint"] = self.fingerprint
        return d
