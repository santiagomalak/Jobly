"""Etapas del pipeline de postulaciones (reemplazan a los 5 estados legados).

La columna `estado` se sigue escribiendo, traducida, para que el cron, el CLI y cualquier
código viejo sigan funcionando. La fuente de verdad del CRM es `etapa`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

ETAPAS = (
    "relevada", "interesa", "postulada", "en_proceso", "entrevista",
    "oferta", "ganada", "rechazada", "descartada", "sin_respuesta",
)

ETIQUETAS = {
    "relevada": "Relevada",
    "interesa": "Interesa",
    "postulada": "Postulada",
    "en_proceso": "En proceso",
    "entrevista": "Entrevista / negociación",
    "oferta": "Oferta",
    "ganada": "Ganada",
    "rechazada": "Rechazada",
    "descartada": "Descartada",
    "sin_respuesta": "Sin respuesta",
}

# Etapas que implican que la propuesta se envió (cuentan para métricas y racha).
ENVIADAS = ("postulada", "en_proceso", "entrevista", "oferta", "ganada", "rechazada", "sin_respuesta")
ABIERTAS = ("postulada", "en_proceso", "entrevista", "oferta")
CERRADAS = ("ganada", "rechazada", "descartada", "sin_respuesta")
RESPONDIDAS = ("en_proceso", "entrevista", "oferta", "ganada", "rechazada")

# Probabilidad de cierre por etapa (pipeline ponderado). Punto de partida razonable para
# propuestas en frío; config.yaml puede pisarlo con `probabilidades`.
PROBABILIDAD = {"postulada": 0.05, "en_proceso": 0.2, "entrevista": 0.4, "oferta": 0.7, "ganada": 1.0}

_A_ESTADO = {
    "relevada": "nuevo", "interesa": "nuevo",
    "postulada": "postulado",
    "en_proceso": "respondido", "entrevista": "respondido", "oferta": "respondido",
    "ganada": "ganado",
    "rechazada": "perdido", "descartada": "perdido", "sin_respuesta": "perdido",
}

_DE_ESTADO = {"nuevo": "relevada", "postulado": "postulada", "respondido": "en_proceso", "ganado": "ganada", "perdido": "rechazada"}

# Política de seguimiento (memoria/06_plantillas_venta.md para freelance): días desde la
# postulación para el seguimiento 1 y el 2. Después del 2, se espera `CIERRE` días más y
# la postulación pasa sola a "sin respuesta".
SEGUIMIENTO = {"freelance": (2, 6), "empleo": (7, 14)}
CIERRE = {"freelance": 4, "empleo": 7}

# Argentina no tiene horario de verano: UTC-3 fijo.
ART = timezone(timedelta(hours=-3))


def a_estado(etapa: str) -> str:
    return _A_ESTADO.get(etapa, "nuevo")


def de_estado(estado: str) -> str:
    return _DE_ESTADO.get(estado, "relevada")


def ahora_art() -> datetime:
    return datetime.now(ART)


def dias_seguimiento(tipo: str | None) -> tuple[int, int]:
    return SEGUIMIENTO.get(tipo or "freelance", SEGUIMIENTO["freelance"])
