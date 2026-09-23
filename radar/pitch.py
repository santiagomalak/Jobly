"""Generación del pitch comercial de 3 párrafos."""
from __future__ import annotations

import re

from . import llm
from .memory import Memory
from .models import Ticket

SYSTEM = """Sos el redactor comercial de Santiago, un ingeniero de automatización y datos freelance.
Escribís propuestas de primer contacto para proyectos freelance.

REGLAS INVIOLABLES:
1. Exactamente 3 párrafos. Entre 90 y 140 palabras en total. Ni un párrafo más.
2. Párrafo 1 = DIAGNÓSTICO: reformulás el problema del cliente con precisión técnica y nombrás
   una dificultad real que él NO mencionó. Nunca empieza con "yo" ni con un saludo.
3. Párrafo 2 = PLAN: 2 frases + 3 bullets concretos (herramienta, entregable, plazo en días).
   Números reales, nada de "podría", "quizás" o "dependiendo".
4. Párrafo 3 = PRUEBA + CIERRE: mencionás UNA prueba/proyecto análogo y cerrás con UNA sola
   pregunta técnica que sea fácil de responder.
5. Escribís SOLO sobre el módulo de skills que te paso. Si el ticket es de n8n, no existe dbt,
   React ni ciberseguridad en tu respuesta.
6. Idioma: el mismo del ticket (inglés → inglés, español → español, portugués → portugués).
7. PROHIBIDO: saludos genéricos, "hope this finds you well", "passionate developer", emojis,
   listar todo el stack, mencionar que sos estudiante, disculparte, "quedo a disposición".
8. Devolvés ÚNICAMENTE el texto de la propuesta. Sin encabezados, sin comillas, sin explicar
   lo que hiciste, sin decir "aquí está la propuesta".
"""

USER_TEMPLATE = """### TICKET
Título: {title}
Fuente: {source}
Presupuesto detectado: {budget}
Descripción:
{description}

### MI MEMORIA RELEVANTE (usá SOLO esto)
{context}

### INSTRUCCIÓN
Escribí la propuesta de primer contacto de 3 párrafos.
Cotizá dentro del rango del módulo, coherente con el presupuesto detectado.
Si no hay una PoC publicada para este módulo, describí el proyecto análogo sin inventar un link.
Los ÚNICOS trabajos pasados que podés mencionar son los de PROYECTOS REALES, con los datos exactos con que figuran ahí: no agregues cifras, clientes, integraciones ni funciones que no estén escritas. Si ninguno se parece de verdad al pedido, no cites ninguno y cerrá solo con la pregunta técnica.
"""


def _fallback(ticket: Ticket, mem: Memory) -> str:
    """Pitch sin IA: usable tal cual, refinable en el canal copiloto."""
    modulo = ticket.module or "AUTOMATION"
    bloque = mem.modulo(modulo)
    m = re.search(r"## Pitch de una línea\n(.+)", bloque)
    una_linea = m.group(1).strip().strip('"') if m else ""
    sec = re.search(r"## Preguntas de calificación.*?\n(.*?)(?=\n## |\Z)", bloque, re.S)
    preguntas = re.findall(r"^\d\.\s(.+)$", sec.group(1), re.M) if sec else []
    primera = preguntas[0] if preguntas else "¿Cuál es el alcance exacto que tenés en mente?"
    rango = "USD 150–350"
    if ticket.budget_usd:
        rango = f"USD {ticket.budget_usd}–{int(ticket.budget_usd * 1.25)}"

    return (
        f"[BORRADOR SIN IA — refinar en #03-copiloto-chat]\n\n"
        f"Por lo que describís, el punto crítico de «{ticket.title[:70]}» no es la parte visible "
        f"sino lo que pasa cuando el proceso falla a mitad de camino: ahí es donde estas "
        f"implementaciones se rompen en silencio.\n\n"
        f"{una_linea}\n"
        f"• Entregable principal funcionando y desplegado\n"
        f"• Manejo de errores con alerta cuando algo falla\n"
        f"• Documentación + video corto para que quede tuyo\n"
        f"Plazo: 1–3 días hábiles. Rango: {rango}.\n\n"
        f"{'Tengo trabajo real comparable y te lo puedo mostrar funcionando. ' if mem.proyectos_reales(modulo) else ''}"
        f"{primera}"
    )


def build_pitch(ticket: Ticket, mem: Memory) -> Ticket:
    context = mem.contexto_pitch(ticket.module)
    user = USER_TEMPLATE.format(
        title=ticket.title,
        source=ticket.source,
        budget=f"USD {ticket.budget_usd}" if ticket.budget_usd else "no publicado",
        description=(ticket.description or "(sin descripción)")[:2500],
        context=context[:9000],
    )
    result = llm.generate(SYSTEM, user, fallback=_fallback(ticket, mem))
    ticket.pitch = result.text
    ticket.pitch_engine = result.engine
    return ticket
