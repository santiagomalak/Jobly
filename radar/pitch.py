"""Generación del pitch comercial de 3 párrafos."""
from __future__ import annotations

import re

from . import ask as asistente
from . import llm
from .memory import Memory
from .models import Ticket
from .scoring import es_oferta_de_empleo

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


SYSTEM_EMPLEO = """Sos Santiago Aragón Malak, ingeniero de datos y automatización, y escribís una carta de postulación breve para un PUESTO (relación de dependencia o contrato), no para un proyecto puntual.

REGLAS INVIOLABLES:
1. Exactamente 3 párrafos, 100 a 150 palabras en total. Sin saludo ni despedida.
2. Párrafo 1 = ENCAJE: qué pide el puesto y por qué tu experiencia real responde a eso. Concreto, sin adjetivos vacíos ("apasionado", "dinámico").
3. Párrafo 2 = PRUEBA: UNA experiencia o proyecto de la sección PROYECTOS REALES, con sus datos exactos. Si ninguno se parece de verdad al puesto, describí una capacidad concreta del CONTEXTO sin atribuirla a un empleo.
4. Párrafo 3 = DISPONIBILIDAD + cierre con UNA pregunta específica sobre el rol o el equipo.
5. Usá SOLO hechos del CONTEXTO. Nunca inventes empleos, cifras, títulos ni niveles; los niveles se copian textuales del CV y, ante dudas, el más bajo. Lo que falte se escribe [COMPLETAR: dato].
6. Idioma: el del aviso.
7. PROHIBIDO: precios, tarifas, plazos de entrega en días, saludos genéricos, "hope this finds you well", emojis, decir que sos estudiante, disculparte.
8. Devolvés ÚNICAMENTE el texto, sin encabezados ni comillas.
"""

USER_TEMPLATE_EMPLEO = """### PUESTO
Título: {title}
Fuente: {source}
Datos: {datos}
Descripción:
{description}

### CONTEXTO (mis datos reales)
{context}

### INSTRUCCIÓN
Escribí la carta de postulación de 3 párrafos para este puesto.
"""


def _proyecto_real(ticket: Ticket, mem: Memory) -> str:
    m = re.search(r"\*\*(.+?)\*\*", mem.proyectos_reales(ticket.module or ""))
    return m.group(1).strip() if m else ""


def _fallback_empleo(ticket: Ticket, mem: Memory) -> str:
    """Carta sin IA: honesta y corta. Hay que completarla a mano."""
    proyecto = _proyecto_real(ticket, mem)
    kws = ", ".join(ticket.matched_keywords[:4])
    return (
        "[BORRADOR SIN IA — completá y revisá antes de enviar]\n\n"
        f"Me postulo a «{ticket.title[:80]}». Mi trabajo se centra en datos y automatización"
        f"{' (' + kws + ')' if kws else ''}, y lo que pide el puesto se cruza con lo que hago hoy.\n\n"
        f"{'Como prueba concreta: ' + proyecto + '.' if proyecto else '[COMPLETAR: la experiencia más parecida al puesto]'}\n\n"
        "Trabajo 100% remoto desde Argentina (UTC-3). ¿Cuál es el proceso de selección y con qué "
        "stack trabaja hoy el equipo?"
    )


def _build_pitch_empleo(ticket: Ticket, mem: Memory) -> Ticket:
    datos = "; ".join(t.split(":", 1)[1] for t in ticket.tags if t.split(":", 1)[0] in ("tipo", "ubicacion", "seniority", "salario"))
    user = USER_TEMPLATE_EMPLEO.format(
        title=ticket.title,
        source=ticket.source,
        datos=datos or "sin datos",
        description=(ticket.description or "(sin descripción)")[:2500],
        context=asistente.contexto_asistente(mem, ticket.text)[:12000],
    )
    result = llm.generate(SYSTEM_EMPLEO, user, fallback=_fallback_empleo(ticket, mem))
    ticket.pitch, ticket.pitch_engine = result.text, result.engine
    return ticket


def build_pitch(ticket: Ticket, mem: Memory) -> Ticket:
    if es_oferta_de_empleo(ticket):  # un puesto se postula con carta, no con plan de 1-3 días
        return _build_pitch_empleo(ticket, mem)
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
