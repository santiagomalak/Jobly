"""Prueba el motor de scoring y el pitch sin depender de internet.

  python scripts/selftest.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar.config import load_config  # noqa: E402
from radar.memory import Memory  # noqa: E402
from radar.models import Ticket  # noqa: E402
from radar.pitch import build_pitch  # noqa: E402
from radar.scoring import score_ticket  # noqa: E402

FIXTURES = [
    Ticket(
        source="fixture",
        title="Need n8n expert to build CRM to WhatsApp integration - urgent",
        url="https://example.com/1",
        description=(
            "We use Bitrix24 as our CRM and need an n8n workflow that pushes new leads to "
            "WhatsApp and keeps both systems in sync. There is webhook support on both sides. "
            "Around 200 records per day. Budget is $350 fixed price, needs to be done this week. "
            "Documentation included would be a plus."
        ),
        raw_budget="Budget: $350",
    ),
    Ticket(
        source="fixture",
        title="dbt + BigQuery analytics engineer for small ecommerce data warehouse",
        url="https://example.com/2",
        description=(
            "Our data is in BigQuery but the models are a mess. We need a proper dbt project "
            "with staging and marts layers, tests, and a Metabase dashboard on top with our "
            "main KPIs. Budget USD 400."
        ),
        raw_budget="USD 400",
    ),
    Ticket(
        source="fixture",
        title="Python web scraping - extract product prices from 3 sites",
        url="https://example.com/3",
        description=(
            "Need a scraper using Playwright that handles pagination and login on three "
            "ecommerce sites, output to CSV, running daily. $200."
        ),
        raw_budget="$200",
    ),
    Ticket(
        source="fixture",
        title="Looking for full time senior developer, must be US based",
        url="https://example.com/4",
        description="Full-time employee position, React and Node, must be US citizen. $120k/year.",
    ),
    Ticket(
        source="fixture",
        title="Build crypto trading bot with AI signals",
        url="https://example.com/5",
        description="Need a crypto trading bot that predicts the market. Equity only for now.",
    ),
    Ticket(
        source="fixture",
        title="Fix my wordpress theme",
        url="https://example.com/6",
        description="Wordpress theme customization needed, $30.",
    ),
]


def _ticket(desc: str, title: str = "n8n workflow automation with webhook", tags=None) -> Ticket:
    return Ticket(source="t", title=title, url="https://example.com/x", description=desc, tags=tags or [])


def checks_motor(cfg: dict, tax: dict) -> None:
    """Regresiones del motor de scoring. Sin internet ni LLM."""
    from radar.scoring import extract_budget

    # Presupuestos: sueldo anual no es presupuesto, miles con coma y sufijo k
    assert extract_budget("$90k - $105k") is None, "un sueldo anual no es un presupuesto de proyecto"
    assert extract_budget("Budget $1,500 fixed") == 1500
    assert extract_budget("Budget: $500") == 500
    assert extract_budget("USD 300") == 300

    largo = " Need a clean integration between our CRM and Google Sheets, documentation included. " * 2

    # El killer "$5" no puede matar "$500" (subcadena) ni "$5,000"
    for monto in ("$500", "$5,000"):
        t = score_ticket(_ticket(f"Budget {monto}." + largo), tax, cfg)
        assert not (t.reasons and str(t.reasons[0]).startswith("killer")), f"killer por subcadena con {monto}"
    t = score_ticket(_ticket("Pay is $5 total." + largo), tax, cfg)
    assert t.reasons[0].startswith("killer"), "el killer '$5' debe seguir matando $5 real"

    # Keywords cortas: "rag" no es "average", "bot" no es "both"
    t = score_ticket(_ticket("Average brag storage both sides.", title="Marketing role"), tax, cfg)
    assert t.module == "" and t.verdict == "discard", f"falso positivo por subcadena: {t.matched_keywords}"

    # Ubicación: un aviso solo para Europa penaliza; uno que incluye Argentina no
    base = "n8n workflow automation webhook integration crm. Budget $300." + largo
    eu = score_ticket(_ticket(base, tags=["ubicacion:Europe"]), tax, cfg)
    ar = score_ticket(_ticket(base, tags=["ubicacion:USA, Canada, Argentina"]), tax, cfg)
    assert eu.score == ar.score - 30, "la ubicación sin Argentina/LATAM debe restar 30"
    assert any("ubicación" in r for r in eu.reasons)

    # Años exigidos
    junior = score_ticket(_ticket(base), tax, cfg)
    senior = score_ticket(_ticket(base + " 8+ years of experience."), tax, cfg)
    assert senior.score < junior.score, "pedir 8+ años debe penalizar"

    # Contexto del pitch: nada de PoCs pendientes ni proyectos de otro módulo
    mem = Memory(Path(cfg["root"]) / cfg["memory_dir"])
    ctx_auto = mem.contexto_pitch("AUTOMATION")
    assert "dbt-ecommerce-starter" not in ctx_auto, "una PoC PENDIENTE llegó al prompt"
    assert "Olist" not in ctx_auto, "un proyecto DATA llegó al prompt de AUTOMATION"
    assert "Olist" in mem.contexto_pitch("DATA")


def main() -> int:
    cfg = load_config()
    mem = Memory(Path(cfg["root"]) / cfg["memory_dir"])
    tax = mem.taxonomia()
    checks_motor(cfg, tax)
    print("checks del motor OK")

    print("=" * 74)
    print("SCORING")
    print("=" * 74)
    aprobados = []
    for t in FIXTURES:
        score_ticket(t, tax, cfg)
        mark = "PASA " if t.verdict == "pass" else "corta"
        print(f"[{mark}] {t.score:>3} · {t.module or '—':<11} · {t.title[:52]}")
        print(f"         {'; '.join(t.reasons)[:150]}")
        if t.verdict == "pass":
            aprobados.append(t)

    print()
    print("=" * 74)
    print(f"PITCH (motor disponible: se usa el primero que responda)")
    print("=" * 74)
    for t in aprobados[:2]:
        build_pitch(t, mem)
        print(f"\n--- {t.module} · motor: {t.pitch_engine} ---")
        print(t.pitch)

    assert aprobados, "Ningún fixture pasó el filtro: revisá 08_taxonomia_keywords.md"
    assert all(t.verdict == "discard" for t in FIXTURES[3:]), "Los killers no están filtrando"
    print("\n✅ selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
