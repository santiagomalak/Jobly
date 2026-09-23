"""Mensajes de seguimiento según la política de memoria/06_plantillas_venta.md:
1 a las 48 h sin respuesta (2 frases que aportan valor), 2 a los 6 días (1 frase que cierra).
Máximo 2. Después, silencio: perseguir baja tu precio.
"""
from __future__ import annotations

from . import llm
from .memory import Memory
from .models import Ticket
from .scoring import es_oferta_de_empleo

SYSTEM = """Sos Santiago Aragón Malak y escribís un mensaje de SEGUIMIENTO a una postulación que no tuvo respuesta.

REGLAS INVIOLABLES:
1. Respetá exactamente la estructura pedida (cantidad de frases). Sin saludo, sin despedida, sin disculpas, sin emojis.
2. Mismo idioma que el aviso.
3. Nunca inventes estadísticas, porcentajes, cifras, clientes ni proyectos. Un aporte técnico es una observación cualitativa y concreta sobre el problema del aviso, no un dato numérico.
4. Lo que dependa de vos y no esté en el contexto (un día para arrancar, disponibilidad) se escribe [COMPLETAR: dato].
5. Devolvés ÚNICAMENTE el texto del mensaje.
"""

_PEDIDO = {
    (False, 1): "Seguimiento 1 (48 h sin respuesta), EXACTAMENTE 2 frases. Frase 1: un aporte técnico útil y concreto sobre el problema de este aviso, sin cifras. Frase 2: si el proyecto sigue abierto, ofrecé arrancar un día concreto.",
    (False, 2): "Seguimiento 2 (6 días), EXACTAMENTE 1 frase que cierra el loop: cerrás tu agenda de esta semana y preguntás si lo dejás reservado o lo das de baja.",
    (True, 1): "Seguimiento 1 a una postulación a un PUESTO (48 h sin respuesta), EXACTAMENTE 2 frases: reafirmás tu interés con un motivo concreto del puesto y preguntás cómo sigue el proceso.",
    (True, 2): "Seguimiento 2 a una postulación a un PUESTO (6 días), EXACTAMENTE 1 frase cordial que cierra: quedás atento a novedades si el puesto sigue abierto.",
}

_FALLBACK = {
    (False, 1): "Te dejo algo por si te sirve igual: [COMPLETAR: un aporte técnico concreto sobre el problema]. Si el proyecto sigue abierto, puedo arrancar [COMPLETAR: día].",
    (False, 2): "Cierro mi agenda de esta semana. ¿Lo dejo reservado o lo doy de baja?",
    (True, 1): "Quería saber si hay novedades sobre mi postulación a «{titulo}» y cómo sigue el proceso de selección.",
    (True, 2): "Cierro mi seguimiento por acá; si el puesto sigue abierto, quedo atento a cualquier novedad.",
}


def redactar(ticket: Ticket, numero: int, mem: Memory) -> tuple[str, str]:
    """Devuelve (texto, motor). `numero` es 1 o 2."""
    if numero not in (1, 2):
        raise ValueError("Solo hay 2 seguimientos: después, silencio")
    empleo = es_oferta_de_empleo(ticket)
    fallback = _FALLBACK[(empleo, numero)].format(titulo=ticket.title[:80])
    user = (
        f"### AVISO\nTítulo: {ticket.title}\nDescripción:\n{(ticket.description or '')[:2000]}\n\n"
        f"### MI PERFIL\n{mem.perfil_core()}\n\n### PEDIDO\n{_PEDIDO[(empleo, numero)]}\n"
    )
    res = llm.generate(SYSTEM, user, fallback=fallback, min_len=10)
    return res.text, res.engine
