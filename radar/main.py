"""CLI del radar.

  python -m radar.main run            # corrida completa
  python -m radar.main run --dry      # sin enviar a Discord, imprime en consola
  python -m radar.main doctor         # verifica config, memoria, LLMs y webhook
  python -m radar.main stats          # métricas acumuladas
  python -m radar.main pitch <url>              # regenera el pitch de un ticket guardado
  python -m radar.main marcar <fingerprint> <estado>  # nuevo|postulado|respondido|ganado|perdido
  python -m radar.main dashboard      # genera y abre el CRM (data/dashboard.html)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import webbrowser
from pathlib import Path

from . import llm, notify
from .config import discord_webhook, load_config
from .dashboard import write_dashboard
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


ESTADOS = ("nuevo", "postulado", "respondido", "ganado", "perdido")


def _append_log_proyectos(root: Path, row, estado: str) -> None:
    """Agrega una entrada de postulación a memoria/04_log_proyectos.md (pendiente #5 de CLAUDE.md)."""
    from datetime import date

    log_path = root / "memoria" / "04_log_proyectos.md"
    if not log_path.exists():
        log.warning("no existe %s, no se registra la marca", log_path)
        return

    presupuesto = f"USD {row['budget_usd']}" if row["budget_usd"] else "no publicado"
    entrada = (
        f"\n### [{row['fingerprint'][:8]}] {date.today().isoformat()} — {row['title']}\n"
        f"- Fuente: {row['source']}   | URL: {row['url']}\n"
        f"- Módulo activado: {row['module']}\n"
        f"- Score del radar: {row['score']}\n"
        f"- Presupuesto publicado: {presupuesto}  | Mi cotización: \n"
        f"- Enviado: {date.today().isoformat() if estado != 'nuevo' else ''}  | Respuesta: \n"
        f"- Estado: {estado}\n"
        f"- Resultado / motivo de pérdida: \n"
        f"- APRENDIZAJE (1 línea accionable): \n"
    )
    contenido = log_path.read_text(encoding="utf-8")
    marcador = "\n## Proyectos entregados"
    if marcador in contenido:
        contenido = contenido.replace(marcador, entrada + marcador, 1)
    else:
        contenido += entrada
    log_path.write_text(contenido, encoding="utf-8")


def cmd_marcar(args: argparse.Namespace) -> int:
    cfg = load_config()
    root = Path(cfg["root"])
    store = Store(root / cfg["db_path"])
    row = store.get(args.fingerprint)
    if row is None:
        print(f"No encontré ningún ticket con fingerprint '{args.fingerprint}'")
        store.close()
        return 1
    store.marcar(args.fingerprint, args.estado)
    _append_log_proyectos(root, row, args.estado)
    store.close()
    print(f"[{row['fingerprint'][:8]}] {row['title'][:60]} -> {args.estado}")
    print(f"Registrado en memoria/04_log_proyectos.md")
    return 0


def cmd_pitch(args: argparse.Namespace) -> int:
    cfg = load_config()
    root = Path(cfg["root"])
    store = Store(root / cfg["db_path"])
    row = store.get_by_url(args.url)
    store.close()
    if row is None:
        print(f"No encontré ningún ticket guardado con url '{args.url}'")
        return 1

    data = json.loads(row["payload"])
    data.pop("fingerprint", None)
    ticket = Ticket(**data)
    mem = Memory(root / cfg["memory_dir"])
    build_pitch(ticket, mem)
    print(f"motor: {ticket.pitch_engine}\n")
    print(ticket.pitch)
    return 0


def cmd_dashboard(_: argparse.Namespace) -> int:
    cfg = load_config()
    root = Path(cfg["root"])
    store = Store(root / cfg["db_path"])
    out_path = root / "data" / "dashboard.html"
    write_dashboard(store, cfg, out_path)
    store.close()
    print(f"CRM generado en {out_path}")
    webbrowser.open(out_path.resolve().as_uri())
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
    sub.add_parser("dashboard", help="genera y abre el CRM").set_defaults(func=cmd_dashboard)

    p_marcar = sub.add_parser("marcar", help="actualiza el estado de un ticket y lo registra en el log")
    p_marcar.add_argument("fingerprint")
    p_marcar.add_argument("estado", choices=ESTADOS)
    p_marcar.set_defaults(func=cmd_marcar)

    p_pitch = sub.add_parser("pitch", help="regenera el pitch de un ticket guardado")
    p_pitch.add_argument("url")
    p_pitch.set_defaults(func=cmd_pitch)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
