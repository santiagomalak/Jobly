"""CRM: dashboard HTML estático generado desde la DB. Sin dependencias nuevas,
sin servidor — se regenera y se abre en el navegador. Fase 1 del roadmap de
docs/VISION.md: simple, gratis, funcional.
"""
from __future__ import annotations

import html
import json
from datetime import datetime, timedelta, timezone

from .store import Store

ESTADOS = ["nuevo", "postulado", "respondido", "ganado", "perdido"]

_ESTADO_COLOR = {
    "nuevo": "#3b82f6",
    "postulado": "#f59e0b",
    "respondido": "#a855f7",
    "ganado": "#22c55e",
    "perdido": "#6b7280",
}


def _esc(s: object) -> str:
    return html.escape(str(s or ""))


def _rows_by_estado(rows: list) -> dict[str, list]:
    out: dict[str, list] = {e: [] for e in ESTADOS}
    for r in rows:
        out.setdefault(r["estado"] or "nuevo", []).append(r)
    for e in out:
        out[e].sort(key=lambda r: r["score"] or 0, reverse=True)
    return out


def _ticket_card(r) -> str:
    fp = r["fingerprint"]
    color = _ESTADO_COLOR.get(r["estado"] or "nuevo", "#6b7280")
    budget = f"USD {r['budget_usd']}" if r["budget_usd"] else "sin dato"
    return f"""
    <div class="card" style="border-left-color:{color}">
      <div class="card-title"><a href="{_esc(r['url'])}" target="_blank">{_esc(r['title'])[:90]}</a></div>
      <div class="card-meta">
        <span class="badge">{_esc(r['module'] or '—')}</span>
        <span class="badge">score {_esc(r['score'])}</span>
        <span class="badge">{_esc(r['source'])}</span>
        <span class="badge">{_esc(budget)}</span>
      </div>
      <div class="card-fp" title="fingerprint completo">
        <code>{_esc(fp)}</code>
        <button class="copybtn" onclick="navigator.clipboard.writeText('python -m radar.main marcar {_esc(fp)} ')">
          copiar comando marcar
        </button>
      </div>
    </div>"""


def build_html(store: Store, cfg: dict) -> str:
    rows = store.all_tickets()
    stats = store.stats()
    # El pipeline (kanban) es solo para oportunidades reales: tickets que pasaron
    # el filtro de scoring. Los descartados quedan afuera (son ruido, no pipeline).
    pipeline_rows = [r for r in rows if r["verdict"] == "pass"]
    by_estado = _rows_by_estado(pipeline_rows)

    hoy = datetime.now(timezone.utc)
    hace_7d = hoy.replace(tzinfo=None) - timedelta(days=7)

    def _parse_seen_at(value: str):
        try:
            return datetime.fromisoformat(value.replace("Z", "")).replace(tzinfo=None)
        except (ValueError, AttributeError):
            return None

    nuevos_semana = sum(
        1 for r in pipeline_rows
        if (dt := _parse_seen_at(r["seen_at"])) and dt >= hace_7d
    )

    ganados = by_estado.get("ganado", [])
    facturado_estimado = sum(g["budget_usd"] or 0 for g in ganados)
    meta_mensual = 900
    progreso_pct = min(100, round(facturado_estimado / meta_mensual * 100)) if meta_mensual else 0

    kpis = [
        ("Total tickets vistos", stats.get("total", 0)),
        ("Nuevos (últimos 7 días)", nuevos_semana),
        ("Aprobados por el scoring", stats.get("aprobados", 0)),
        ("Postulados", stats.get("postulados", 0)),
        ("Notificados a Discord", stats.get("notificados", 0)),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="kpi-num">{v}</div><div class="kpi-label">{_esc(k)}</div></div>'
        for k, v in kpis
    )

    columnas_html = ""
    for estado in ESTADOS:
        items = by_estado.get(estado, [])
        cards = "".join(_ticket_card(r) for r in items[:40]) or '<div class="empty">vacío</div>'
        color = _ESTADO_COLOR[estado]
        columnas_html += f"""
        <div class="column">
          <div class="column-header" style="color:{color}">{estado.upper()} <span class="count">{len(items)}</span></div>
          {cards}
        </div>"""

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Jobly — CRM</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; padding:24px; background:#0b0d12; color:#e5e7eb;
         font-family: -apple-system, "Segoe UI", Roboto, sans-serif; }}
  h1 {{ font-size:22px; margin:0 0 4px; }}
  .sub {{ color:#9ca3af; margin-bottom:20px; font-size:13px; }}
  .kpis {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:24px; }}
  .kpi {{ background:#151922; border:1px solid #262b36; border-radius:10px;
          padding:14px 18px; min-width:140px; }}
  .kpi-num {{ font-size:26px; font-weight:700; }}
  .kpi-label {{ font-size:12px; color:#9ca3af; margin-top:2px; }}
  .progreso-wrap {{ background:#151922; border:1px solid #262b36; border-radius:10px;
                    padding:14px 18px; margin-bottom:24px; }}
  .progreso-bar-bg {{ background:#262b36; border-radius:6px; height:14px; margin-top:8px; overflow:hidden; }}
  .progreso-bar {{ background:linear-gradient(90deg,#22c55e,#4ade80); height:100%; }}
  .board {{ display:grid; grid-template-columns:repeat(5,minmax(220px,1fr));
            gap:12px; overflow-x:auto; }}
  .column {{ background:#0f1218; border:1px solid #1f2430; border-radius:10px; padding:10px; min-height:200px; }}
  .column-header {{ font-weight:700; font-size:13px; margin-bottom:10px;
                     display:flex; justify-content:space-between; }}
  .count {{ background:#1f2430; border-radius:20px; padding:1px 8px; font-size:11px; color:#e5e7eb; }}
  .card {{ background:#151922; border:1px solid #262b36; border-left:3px solid #6b7280;
           border-radius:8px; padding:10px; margin-bottom:8px; }}
  .card-title a {{ color:#e5e7eb; text-decoration:none; font-size:13px; font-weight:600; }}
  .card-title a:hover {{ text-decoration:underline; }}
  .card-meta {{ margin-top:6px; display:flex; gap:6px; flex-wrap:wrap; }}
  .badge {{ background:#1f2430; border-radius:20px; padding:2px 8px; font-size:11px; color:#9ca3af; }}
  .card-fp {{ margin-top:8px; display:flex; align-items:center; gap:6px; }}
  .card-fp code {{ font-size:10px; color:#4b5563; overflow:hidden; text-overflow:ellipsis;
                    white-space:nowrap; max-width:90px; display:inline-block; }}
  .copybtn {{ font-size:10px; background:#1f2430; border:1px solid #333a48; color:#9ca3af;
              border-radius:6px; padding:3px 6px; cursor:pointer; }}
  .copybtn:hover {{ background:#262b36; color:#e5e7eb; }}
  .empty {{ color:#4b5563; font-size:12px; text-align:center; padding:20px 0; }}
</style></head>
<body>
  <h1>Jobly — CRM</h1>
  <div class="sub">Generado {_esc(hoy.strftime('%Y-%m-%d %H:%M UTC'))} · regenerá con <code>python -m radar.main dashboard</code></div>

  <div class="kpis">{kpi_html}</div>

  <div class="progreso-wrap">
    <div style="display:flex;justify-content:space-between;font-size:13px;">
      <span>Progreso hacia el piso mensual (USD {meta_mensual})</span>
      <span>USD {facturado_estimado} estimado de tickets "ganado"</span>
    </div>
    <div class="progreso-bar-bg"><div class="progreso-bar" style="width:{progreso_pct}%"></div></div>
  </div>

  <div class="board">{columnas_html}</div>
</body></html>"""


def write_dashboard(store: Store, cfg: dict, out_path) -> None:
    html_content = build_html(store, cfg)
    out_path.write_text(html_content, encoding="utf-8")
