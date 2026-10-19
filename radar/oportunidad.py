"""Score de oportunidad 0-100: ¿dónde conviene poner el tiempo HOY para llegar a la meta?

Complementa al score del radar (scoring.py, que filtra ruido): este ordena lo que ya pasó el
filtro según encaje, plata, tiempo, cliente, región, idioma, seniority, valor de portfolio y
competencia. Es determinístico y explicable: cada punto queda en `detalle`.
Lo desconocido puntúa neutro (ni premia ni castiga): un aviso del cron sin datos de cliente
no pierde contra uno importado que sí los trae, salvo que esos datos sean buenos.
"""
from __future__ import annotations

import re
from typing import Any

from .models import Ticket
from .scoring import es_oferta_de_empleo
from . import fit

# Conversión aproximada a USD. Pisable en config.yaml (`tipos_cambio`). Sin tipo = monto desconocido.
TIPOS_CAMBIO = {"USD": 1.0, "US$": 1.0, "EUR": 1.08, "BRL": 0.18, "GBP": 1.27, "CAD": 0.73, "MXN": 0.054}

_REGION_OK = re.compile(r"worldwide|anywhere|global|latam|latin|south america|americas|argentina|remote|remoto", re.I)
_EN = re.compile(r"\b(the|and|with|you|we|our|for|will|experience|looking)\b", re.I)
_ES_PT = re.compile(r"\b(el|los|las|con|para|que|una|experiencia|buscamos|você|não|para|com|uma)\b", re.I)
_INGLES_HABLADO = re.compile(r"fluent english|english.{0,20}(fluent|c1|c2|native)|requiere ingl[eé]s hablado|calls? in english|ingl[eé]s fluido", re.I)
_PORTFOLIO = re.compile(r"\b(llm|ai|ia|openai|gpt|rag|agent|dashboard|power bi|dbt|etl|pipeline|automat|n8n|react|next\.?js|analytics|machine learning)\b", re.I)

_NIVEL_ALTO = {"senior", "lead", "staff", "principal", "manager", "director"}
_NIVEL_OK = {"junior", "semi", "semi-senior", "mid", "entry-level", "entry level", "intern", "trainee"}


def _tag(t: Ticket, clave: str) -> str:
    for tag in t.tags:
        if tag.startswith(clave + ":"):
            return tag.split(":", 1)[1].strip()
    return ""


def tipo_de(t: Ticket) -> str:
    tipo = str(t.extra.get("tipo") or "").lower()
    if tipo in ("empleo", "freelance"):
        return tipo
    return "empleo" if es_oferta_de_empleo(t) else "freelance"


def monto_usd(t: Ticket, cfg: dict[str, Any] | None = None) -> tuple[int | None, str]:
    """(monto en USD, periodo). Usa el extremo bajo del rango, como el radar (pesimismo deliberado)."""
    x = t.extra
    bajo = x.get("presupuesto_min") or x.get("presupuesto_max")
    periodo = str(x.get("periodo_pago") or "").lower() or "proyecto"
    if bajo is None:
        return (t.budget_usd, "proyecto") if t.budget_usd else (None, periodo)
    moneda = str(x.get("moneda") or "USD").upper()
    cambio = {**TIPOS_CAMBIO, **((cfg or {}).get("tipos_cambio") or {})}.get(moneda)
    if cambio is None:
        return None, periodo
    return int(round(float(bajo) * float(cambio))), periodo


def idioma_de(t: Ticket) -> str:
    dado = str(t.extra.get("idioma") or "").lower()[:2]
    if dado in ("es", "pt", "en"):
        return dado
    texto = t.text[:3000]
    return "en" if len(_EN.findall(texto)) > len(_ES_PT.findall(texto)) else "es"


def calcular(t: Ticket, perfil: str, cfg: dict[str, Any] | None = None) -> tuple[int, list[list[Any]]]:
    """Devuelve (score 0-100, detalle [[componente, puntos, máximo, nota], ...])."""
    x = t.extra
    tipo = tipo_de(t)
    detalle: list[list[Any]] = []

    def suma(nombre: str, pts: float, maximo: int, nota: str) -> None:
        detalle.append([nombre, int(round(pts)), maximo, nota])

    # 1. Encaje de stack (25)
    enc = fit.encaje_texto(f"{t.text}\n{x.get('stack', '')}\n{x.get('requisitos', '')}".lower(), perfil)
    pedidas = len(enc.tenes) + len(enc.faltan)
    if pedidas:
        suma("Encaje de stack", 25 * len(enc.tenes) / pedidas, 25, f"tenés {len(enc.tenes)} de {pedidas}")
    else:
        suma("Encaje de stack", 12, 25, "no menciona tecnologías concretas")

    # 2. Monto en USD (20)
    monto, periodo = monto_usd(t, cfg)
    piso = int((cfg or {}).get("min_budget_usd", 120))
    if monto is None:
        suma("Monto", 8, 20, "sin monto visible")
    elif periodo == "hora":
        pts = 18 if monto >= 25 else 12 if monto >= 15 else 4
        suma("Monto", pts, 20, f"USD {monto}/h")
    elif periodo == "mes" or tipo == "empleo":
        pts = 20 if monto >= 1500 else 16 if monto >= 900 else 8 if monto >= 600 else 2
        suma("Monto", pts, 20, f"USD {monto}/mes")
    else:
        if monto < piso:
            pts = 0
        elif monto < 150:
            pts = 12
        elif monto <= 450:
            pts = 20
        elif monto <= 1500:
            pts = 15
        else:
            pts = 10
        suma("Monto", pts, 20, f"USD {monto} por proyecto" + (" (bajo tu piso)" if monto < piso else ""))

    # 3. Tiempo estimado (15): prioriza tickets de 1-3 días
    dias = x.get("duracion_dias")
    if tipo == "empleo":
        suma("Tiempo", 8, 15, "puesto: no aplica")
    elif dias is None:
        suma("Tiempo", 7, 15, "duración desconocida")
    else:
        d = float(dias)
        suma("Tiempo", 15 if d <= 3 else 8 if d <= 7 else 4, 15, f"~{d:g} días")

    # 4. Calidad del cliente (15)
    verif, previos, calif = x.get("cliente_verificado"), x.get("proyectos_previos_cliente"), x.get("calificacion_cliente")
    if verif is None and previos is None and calif is None:
        suma("Cliente", 6, 15, "sin datos del cliente")
    else:
        pts = (5 if verif == 1 else 0) + (5 if (previos or 0) >= 5 else 3 if (previos or 0) >= 1 else 0)
        pts += 5 if (calif or 0) >= 4.5 else 3 if (calif or 0) >= 4 else 0
        partes = ["verificado" if verif == 1 else "sin verificar", f"{previos or 0} proyectos previos"]
        if calif:
            partes.append(f"calificación {calif:g}")
        suma("Cliente", pts, 15, ", ".join(partes))

    # 5. Remoto / región (10)
    modalidad = str(x.get("modalidad") or "").lower()
    lugar = str(x.get("pais") or _tag(t, "ubicacion"))
    if modalidad in ("presencial", "hibrido", "híbrido"):
        suma("Remoto / región", 0, 10, f"modalidad {modalidad}")
    elif not lugar:
        suma("Remoto / región", 7, 10, "región no informada")
    elif _REGION_OK.search(lugar):
        suma("Remoto / región", 10, 10, lugar[:40])
    else:
        suma("Remoto / región", 0, 10, f"restringido a {lugar[:40]}")

    # 6. Idioma (5): español nativo, portugués C1, inglés de lectura
    idioma = idioma_de(t)
    if _INGLES_HABLADO.search(f"{t.text} {x.get('notas', '')} {x.get('requisitos', '')}"):
        suma("Idioma", 0, 5, "exige inglés hablado")
    else:
        suma("Idioma", 5 if idioma in ("es", "pt") else 3, 5, {"es": "español", "pt": "portugués", "en": "inglés escrito"}[idioma])

    # 7. Seniority (5)
    nivel = str(x.get("seniority") or _tag(t, "seniority")).lower()
    if not nivel:
        suma("Seniority", 3, 5, "no informado")
    elif any(n in nivel for n in _NIVEL_ALTO):
        suma("Seniority", 0, 5, nivel)
    else:
        suma("Seniority", 5 if any(n in nivel for n in _NIVEL_OK) else 3, 5, nivel)

    # 8. Valor para el portfolio (5)
    hits = {m.group(0).lower() for m in _PORTFOLIO.finditer(f"{t.text} {x.get('stack', '')}")}
    suma("Portfolio", 5 if len(hits) >= 2 else 3 if hits else 0, 5, ", ".join(sorted(hits)[:4]) or "nada que sume")

    # 9. Competencia (-10 a 0)
    propuestas = x.get("propuestas_recibidas")
    if propuestas is not None:
        p = int(propuestas)
        suma("Competencia", 0 if p < 10 else -4 if p < 30 else -10, 0, f"{p} propuestas")

    total = sum(d[1] for d in detalle)
    return max(0, min(100, int(total))), detalle
