"""Evalúa UN ticket suelto (pegado a mano o vía webhook de n8n) y devuelve el pitch.

  python scripts/ingest_one.py '{"title":"...","description":"...","url":"..."}'
  python scripts/ingest_one.py --interactivo
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar.config import load_config  # noqa: E402
from radar.memory import Memory  # noqa: E402
from radar.models import Ticket  # noqa: E402
from radar.pitch import build_pitch  # noqa: E402
from radar.scoring import score_ticket  # noqa: E402
from radar.store import Store  # noqa: E402


def evaluar(data: dict) -> str:
    cfg = load_config()
    root = Path(cfg["root"])
    mem = Memory(root / cfg["memory_dir"])
    ticket = Ticket(
        source=data.get("source", "manual"),
        title=data.get("title", ""),
        url=data.get("url", ""),
        description=data.get("description", ""),
        raw_budget=data.get("raw_budget", "") or data.get("budget", ""),
    )
    score_ticket(ticket, mem.taxonomia(), cfg)
    if ticket.verdict != "pass":
        return (
            f"❌ **DESCARTADO** ({ticket.score}/100) · {ticket.title[:80]}\n"
            f"Motivos: {'; '.join(ticket.reasons)}"
        )
    build_pitch(ticket, mem)
    store = Store(root / cfg["db_path"])
    store.save(ticket, notified=True)
    store.close()
    return (
        f"✅ **{ticket.score}/100** · módulo **{ticket.module}** · motor: {ticket.pitch_engine}\n"
        f"{ticket.url}\n```\n{ticket.pitch[:1500]}\n```"
    )


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] != "--interactivo":
        data = json.loads(sys.argv[1])
    else:
        print("Título del ticket:")
        title = input().strip()
        print("URL (enter para saltar):")
        url = input().strip()
        print("Pegá la descripción y terminá con una línea que diga FIN:")
        lines = []
        while True:
            line = input()
            if line.strip().upper() == "FIN":
                break
            lines.append(line)
        data = {"title": title, "url": url, "description": "\n".join(lines)}
    print(evaluar(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
