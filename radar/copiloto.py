"""Copiloto de ingresos: cuánto llevás, cuánto viene en camino y cuántas propuestas faltan HOY.

Todo sale de las filas que ya trae Store.tablero(): no hace consultas propias.
"""
from __future__ import annotations

import calendar
import math
from datetime import datetime, timedelta
from typing import Any

from . import etapas as et
from .oportunidad import TIPOS_CAMBIO
from .store import _parse_ts, enviada, etapa_de


def _monto(row: Any, cfg: dict[str, Any]) -> int | None:
    """Monto estimado en USD de una postulación (extremo bajo del rango, por proyecto o por mes)."""
    bajo = row["presupuesto_min"] or row["presupuesto_max"]
    if bajo:
        cambio = {**TIPOS_CAMBIO, **(cfg.get("tipos_cambio") or {})}.get(str(row["moneda"] or "USD").upper())
        if cambio is None:
            return None
        valor = float(bajo) * float(cambio)
        if (row["periodo_pago"] or "") == "hora":
            valor *= 20  # ~una semana corta de trabajo: los contratos por hora rara vez duran menos
        return int(valor)
    return row["budget_usd"] or None


def meta(t: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Barra de meta: confirmado (ingresos del mes) + ponderado (pipeline × probabilidad)."""
    ahora: datetime = t["ahora"] - timedelta(hours=3)  # hora de Argentina
    objetivo = int(cfg.get("meta_mensual_usd", 900))
    promedio = int(cfg.get("ticket_promedio_usd", 250))
    probs = {**et.PROBABILIDAD, **(cfg.get("probabilidades") or {})}

    cobrado = sum(i["monto_usd"] for i in t["ingresos_mes"] if i["estado"] == "cobrado")
    acordado = sum(i["monto_usd"] for i in t["ingresos_mes"] if i["estado"] == "acordado")
    con_ingreso = {i["ticket_fp"] for i in t["ingresos_mes"] if i["ticket_fp"]}
    # Ganadas este mes sin ingreso cargado: cuentan por su presupuesto estimado (marcadas aparte)
    mes = ahora.strftime("%Y-%m")
    estimado = 0
    for r in t["por_etapa"]["ganada"]:
        dt = _parse_ts(r["estado_at"])
        if r["fingerprint"] not in con_ingreso and dt and (dt - timedelta(hours=3)).strftime("%Y-%m") == mes:
            estimado += _monto(r, cfg) or 0
    confirmado = cobrado + acordado + estimado

    ponderado, abiertas = 0.0, 0
    for etapa in et.ABIERTAS:
        for r in t["por_etapa"][etapa]:
            abiertas += 1
            ponderado += (_monto(r, cfg) or promedio) * probs.get(etapa, 0)
    ponderado = int(round(ponderado))

    dias_mes = calendar.monthrange(ahora.year, ahora.month)[1]
    restantes = dias_mes - ahora.day + 1  # hoy cuenta
    falta = max(0, objetivo - confirmado - ponderado)

    # Tasa de cierre: real si hay datos suficientes, si no un prior honesto para propuestas en frío.
    enviadas = [r for r in t["rows"] if enviada(r)]
    ganadas = sum(1 for r in enviadas if etapa_de(r) == "ganada")
    minimo = int(cfg.get("min_envios_tasa", 10))
    prior = float(cfg.get("tasa_cierre_prior", 0.05))
    tasa = ganadas / len(enviadas) if len(enviadas) >= minimo and ganadas else prior
    tasa_real = len(enviadas) >= minimo and ganadas > 0
    necesarias = math.ceil(falta / (promedio * tasa)) if falta else 0
    por_dia = math.ceil(necesarias / restantes) if necesarias else 0
    hoy = t["metricas"]["enviadas_hoy"]

    def pct(x: float) -> int:
        return max(0, min(100, round(100 * x / objetivo))) if objetivo else 0

    return {
        "objetivo": objetivo,
        "cobrado": cobrado,
        "acordado": acordado,
        "estimado": estimado,
        "confirmado": confirmado,
        "ponderado": ponderado,
        "abiertas": abiertas,
        "falta": falta,
        "pct_confirmado": pct(confirmado),
        "pct_ponderado": max(0, min(100 - pct(confirmado), pct(ponderado))),
        "dias_restantes": restantes,
        "tasa": tasa,
        "tasa_real": tasa_real,
        "ticket_promedio": promedio,
        "necesarias": necesarias,
        "por_dia": por_dia,
        "hoy": hoy,
        "faltan_hoy": max(0, por_dia - hoy),
        "por_fuente": _por_fuente(enviadas, promedio, falta, restantes, prior, minimo),
    }


def _por_fuente(enviadas: list, promedio: int, falta: int, restantes: int, prior: float, minimo: int) -> list[dict[str, Any]]:
    """Propuestas por día que hacen falta si todo saliera de una sola fuente (con datos reales)."""
    grupos: dict[str, list] = {}
    for r in enviadas:
        grupos.setdefault(r["source"] or "—", []).append(r)
    out = []
    for fuente, rs in grupos.items():
        ganadas = sum(1 for r in rs if etapa_de(r) == "ganada")
        respuestas = sum(1 for r in rs if etapa_de(r) in et.RESPONDIDAS)
        real = len(rs) >= minimo and ganadas > 0
        tasa = ganadas / len(rs) if real else prior
        por_dia = math.ceil(falta / (promedio * tasa) / restantes) if falta else 0
        out.append({"fuente": fuente, "enviadas": len(rs), "respuestas": respuestas, "ganadas": ganadas,
                    "tasa": tasa, "real": real, "por_dia": por_dia})
    return sorted(out, key=lambda f: -f["enviadas"])


def hoy(t: dict[str, Any], limite: int = 10) -> dict[str, Any]:
    """Lo que hay que hacer hoy: acciones vencidas, seguimientos y lo mejor para postular."""
    ahora = t["ahora"]
    fin_de_hoy = (ahora - timedelta(hours=3)).replace(hour=23, minute=59, second=59) + timedelta(hours=3)
    seguimiento_fps = {r["fingerprint"] for r, _, _ in t["seguimientos"]}
    acciones = []
    for r in t["rows"]:
        cuando = _parse_ts(r["proxima_accion_at"])
        if (r["proxima_accion"] and cuando and cuando <= fin_de_hoy and r["fingerprint"] not in seguimiento_fps
                and etapa_de(r) not in et.CERRADAS):
            acciones.append((r, (ahora - cuando).days))
    acciones.sort(key=lambda x: -x[1])
    candidatas = [r for r in t["rows"] if etapa_de(r) in ("interesa", "relevada") and r["verdict"] == "pass"]
    candidatas.sort(key=lambda r: (etapa_de(r) != "interesa", -(r["score_oportunidad"] or 0), -(r["score"] or 0)))
    return {"acciones": acciones, "postular": candidatas[:limite]}
