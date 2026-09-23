"""Asistente de postulaciones: responde preguntas de formularios con TU contexto real.

Es el dolor #1 de postularse en tanda: las mismas preguntas ("qué frameworks conocés",
"por qué querés trabajar con nosotros") en cada formulario. Se pega la pregunta, se pide un
tope de caracteres y sale una respuesta lista para copiar, construida solo con hechos de memoria/.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import llm
from .memory import Memory

SYSTEM = """Sos Santiago Aragón Malak y respondés, en primera persona, una pregunta de un formulario de postulación o de un cliente.

REGLAS INVIOLABLES:
1. Usá SOLO los hechos del CONTEXTO. Si la pregunta pide algo que no está ahí (motivación, salario de un rol fijo, referencias, fechas dudosas), escribí [COMPLETAR: qué dato falta] en ese punto. Nunca inventes empleos, cifras, títulos, clientes, proyectos ni niveles.
2. Respondé en el IDIOMA indicado al final, aunque el contexto esté en español.
3. Directo y concreto: sin saludos, sin "espero que estés bien", sin emojis, sin despedidas, sin explicar lo que hacés. Devolvé SOLO el texto de la respuesta, listo para pegar.
4. Si hay un límite de caracteres, respetalo estrictamente (cuentan los espacios).
5. Si te paso datos de la oferta o empresa, usalos para elegir qué experiencia real destacar, sin inventar afinidad que no exista.
6. Para tecnologías, nombrá solo las que figuran en el contexto. Los niveles (avanzado, intermedio, básico) se copian TEXTUALMENTE de "Stack y nivel"; si una tecnología no tiene nivel ahí o hay dos niveles distintos, usá el más bajo o no lo menciones. Nunca subas un nivel.
7. No le atribuyas a un empleo o proyecto concreto (Ivolution, Olist, StackAdvisor) nada que el contexto no le adjudique explícitamente a ese empleo o proyecto. Las capacidades generales de las secciones EVIDENCIA se pueden afirmar como "trabajo con X", nunca como "en Ivolution hice X" si Ivolution no lo dice.
8. Los números (967 atletas, 13 deportes, 100k+ órdenes) se citan tal cual y con su significado exacto: 967 atletas monitoreados, no 967 usuarios.
"""

USER_TEMPLATE = """### CONTEXTO (mis datos reales)
{contexto}

### OFERTA / EMPRESA (opcional)
{oferta}

### PREGUNTA
{pregunta}

### LÍMITE
{limite}

### IDIOMA DE LA RESPUESTA
{idioma}
"""

FALLBACK = (
    "[IA no disponible en este momento. Respondé a mano con memoria/09_contexto_personal.md "
    "o reintentá en unos minutos.]"
)

_MAX_CONTEXTO = 30_000


@dataclass
class AskResult:
    text: str
    engine: str
    chars: int
    truncated: bool = False
    missing: list[str] = field(default_factory=list)


_PALABRAS = {
    "inglés": {"the", "you", "your", "with", "what", "why", "how", "our", "have", "and", "are",
               "describe", "experience", "work", "do", "please", "years", "tell", "about"},
    "español": {"el", "la", "los", "las", "que", "qué", "con", "por", "para", "tu", "tus",
                "una", "un", "cómo", "cuál", "cuáles", "experiencia", "trabajar", "años", "sos"},
    "portugués": {"você", "voce", "sua", "seu", "para", "com", "uma", "não", "quais", "qual",
                  "experiência", "trabalhar", "anos", "porque", "como", "são"},
}


def detectar_idioma(texto: str) -> str:
    """Heurística por palabras frecuentes; ante empate, español (idioma por defecto)."""
    palabras = re.findall(r"[a-záéíóúñãõçê]+", texto.lower())
    puntos = {idioma: sum(1 for p in palabras if p in vocab) for idioma, vocab in _PALABRAS.items()}
    mejor = max(puntos, key=puntos.get)
    return mejor if puntos[mejor] > puntos["español"] or mejor == "español" else "español"


_PIDE_PLATA = re.compile(
    r"salari|salary|sueldo|\brate\b|tarifa|precio|price|pretensi|expectativ|cobr|hourly|"
    r"por hora|budget|presupuesto|remunerac|compensation|honorari",
    re.I,
)


def _modulos_relevantes(mem: Memory, texto: str, tope: int = 2) -> list[str]:
    """Módulos cuyas keywords (taxonomía) aparecen en la pregunta/oferta, los más fuertes primero."""
    texto = texto.lower()
    puntos: dict[str, int] = {}
    for modulo, kws in mem.taxonomia().get("modulos", {}).items():
        p = sum(3 for k in kws.get("strong", []) if str(k).lower() in texto)
        p += sum(1 for k in kws.get("weak", []) if str(k).lower() in texto)
        if p:
            puntos[modulo] = p
    return sorted(puntos, key=puntos.get, reverse=True)[:tope]


def contexto_asistente(mem: Memory, texto: str = "") -> str:
    """Perfil + contexto personal siempre; evidencia por módulo y tarifas solo si la
    pregunta las toca. Menos tokens por consulta y respuestas más enfocadas."""
    bloques = [
        "=== PERFIL CORE ===", mem.perfil_core(),
        "\n=== CONTEXTO PERSONAL ===", mem.contexto_personal(),
    ]
    if _PIDE_PLATA.search(texto):
        bloques += ["\n=== TARIFAS Y LÍMITES ===", mem.pricing()]
    for modulo in _modulos_relevantes(mem, texto):
        bloques += [f"\n=== EVIDENCIA {modulo} ===", mem.modulo(modulo)]
    return "\n".join(b for b in bloques if b)[:_MAX_CONTEXTO]


def _recortar(texto: str, max_chars: int) -> str:
    """Corta en el último fin de oración (o palabra) que entre en el tope."""
    if len(texto) <= max_chars:
        return texto
    corte = texto[:max_chars]
    fin = max(corte.rfind(". "), corte.rfind(".\n"), corte.rfind("? "), corte.rfind("! "))
    if fin >= max_chars * 0.6:
        return corte[: fin + 1].strip()
    return corte[: corte.rfind(" ")].rstrip(" ,;:") if " " in corte else corte


def answer(pregunta: str, mem: Memory, max_chars: int | None = None, oferta: str = "") -> AskResult:
    pregunta = pregunta.strip()
    if not pregunta:
        raise ValueError("La pregunta está vacía")

    limite = (
        f"Máximo {max_chars} caracteres, contando espacios. Apuntá a unos {int(max_chars * 0.85)}."
        if max_chars
        else "Sin límite: la respuesta más corta que sea completa."
    )
    user = USER_TEMPLATE.format(
        contexto=contexto_asistente(mem, f"{pregunta} {oferta}"),
        oferta=oferta.strip()[:3000] or "(no informada)",
        pregunta=pregunta[:3000],
        limite=limite,
        idioma=detectar_idioma(pregunta),
    )
    res = llm.generate(SYSTEM, user, fallback=FALLBACK, min_len=1)
    texto, truncated = res.text, False

    if max_chars and res.engine != "plantilla" and len(texto) > max_chars:
        reintento = (
            user
            + f"\n### CORRECCIÓN\nTu respuesta anterior tenía {len(texto)} caracteres y el tope es "
            f"{max_chars}. Reescribila completa en menos de {max_chars} caracteres."
        )
        res2 = llm.generate(SYSTEM, reintento, fallback=texto, min_len=1)
        texto = res2.text
        if len(texto) > max_chars:
            texto, truncated = _recortar(texto, max_chars), True

    return AskResult(
        text=texto,
        engine=res.engine,
        chars=len(texto),
        truncated=truncated,
        missing=re.findall(r"\[COMPLETAR:[^\]]*\]", texto),
    )
