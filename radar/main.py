"""CLI del radar.

  python -m radar.main run            # corrida completa
  python -m radar.main run --dry      # sin enviar a Discord, imprime en consola
  python -m radar.main doctor         # verifica config, memoria, LLMs y webhook
  python -m radar.main stats          # métricas acumuladas
  python -m radar.main pitch <url>    # regenera el pitch de un ticket guardado
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import llm, notify
from .config import discord_webhook, load_config
from .memory import Memory
from .models import Ticket
from .pitch import build_pitch
from .scoring import score_ticket
from .sources import collect
from .store import Store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("radar")


def _load_sources(cfg: dict) -> list[dict]:
    path = Path(cfg["root"]) / "sources.yaml"
    if not path.exists():
        log.error("Falta sources.yaml")
        return []
    import yaml

    return (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("sources", [])


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config()
    root = Path(cfg["root"])
    mem = Memory(root / cfg["memory_dir"])
    taxonomy = mem.taxonomia()
    store = Store(root / cfg["db_path"])

    tickets, errores = collect(_load_sources(cfg), cfg)
    log.info("recolectados %d tickets brutos", len(tickets))

    nuevos: list[Ticket] = []
    for t in tickets:
        if store.is_known(t):
            continue
        nuevos.append(t)
    log.info("%d nuevos tras deduplicar", len(nuevos))

    aprobados: list[Ticket] = []
    for t in nuevos:
        score_ticket(t, taxonomy, cfg)
        if t.verdict == "pass":
            aprobados.append(t)
        else:
            store.save(t)

    aprobados.sort(key=lambda x: x.score, reverse=True)
    aprobados = aprobados[: int(cfg.get("max_tickets_per_run", 12))]
    log.info("%d tickets pasaron el filtro", len(aprobados))

    webhook = discord_webhook("propuestas")
    enviados = 0
    for t in aprobados:
        build_pitch(t, mem)
        if args.dry:
            print("\n" + "=" * 72)
            print(f"[{t.score}] {t.module} · {t.title}")
            print(t.url)
            print(f"motor: {t.pitch_engine} · razones: {'; '.join(t.reasons)}")
            print("-" * 72)
            print(t.pitch)
            store.save(t, notified=False)
        else:
            ok = notify.send_ticket(webhook, t)
            enviados += int(ok)
            store.save(t, notified=ok)

    if not args.dry:
        notify.send_summary(
            discord_webhook("radar") or webhook, len(tickets), len(nuevos), enviados, errores
        )
    log.info("listo · enviados=%d errores=%d", enviados, len(errores))
    store.close()
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    cfg = load_config()
    root = Path(cfg["root"])
    ok = True

    print("== Memoria ==")
    try:
        mem = Memory(root / cfg["memory_dir"])
        tax = mem.taxonomia()
        print(f"  módulos en taxonomía : {list(tax['modulos'].keys())}")
        print(f"  killers              : {len(tax['killers'])}")
        print(f"  perfil core          : {len(mem.perfil_core())} chars")
        for m in tax["modulos"]:
            size = len(mem.modulo(m))
            flag = "OK " if size > 200 else "VACÍO"
            print(f"  módulo {m:<11}: {flag} ({size} chars)")
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR: {exc}")
        ok = False

    print("\n== Fuentes ==")
    srcs = _load_sources(cfg)
    print(f"  configuradas: {len(srcs)} · habilitadas: {sum(1 for s in srcs if s.get('enabled', True))}")

    print("\n== LLMs disponibles (cascada) ==")
    for name, available in llm.available().items():
        print(f"  {name:<12}: {'SÍ' if available else 'no configurado'}")

    print("\n== Discord ==")
    for canal in ("radar", "propuestas", "errores"):
        url = discord_webhook(canal)
        print(f"  {canal:<12}: {'configurado' if url else 'FALTA'}")
        if not url and canal == "propuestas":
            ok = False

    print("\n== Base de datos ==")
    try:
        store = Store(root / cfg["db_path"])
        print(f"  {store.stats()}")
        store.close()
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR: {exc}")
        ok = False

    print("\n=> " + ("TODO LISTO" if ok else "HAY COSAS QUE FALTAN (ver arriba)"))
    return 0 if ok else 1


def cmd_stats(_: argparse.Namespace) -> int:
    cfg = load_config()
    store = Store(Path(cfg["root"]) / cfg["db_path"])
    print(json.dumps(store.stats(), indent=2, ensure_ascii=False))
    store.close()
    return 0


def cmd_test_discord(_: argparse.Namespace) -> int:
    webhook = discord_webhook("propuestas")
    if not webhook:
        print("Falta DISCORD_WEBHOOK_PROPUESTAS en .env")
        return 1
    ok = notify.post(
        webhook,
        {"username": "Radar", "content": "Prueba de conexión: el radar te escucha. ✅"},
    )
    print("enviado" if ok else "falló")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="radar")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="corrida completa")
    p_run.add_argument("--dry", action="store_true", help="no envía a Discord, imprime")
    p_run.set_defaults(func=cmd_run)

    sub.add_parser("doctor", help="diagnóstico de configuración").set_defaults(func=cmd_doctor)
    sub.add_parser("stats", help="métricas").set_defaults(func=cmd_stats)
    sub.add_parser("test-discord", help="prueba el webhook").set_defaults(func=cmd_test_discord)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
