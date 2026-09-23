"""Encaje entre un aviso y tu perfil: qué pide que ya tenés, qué menciona que NO figura en tu
memoria, y cuántos años exige. Determinístico (sin LLM): sirve para decidir si postular y
para no prometer en la carta lo que tu perfil no respalda.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .memory import Memory
from .models import Ticket
from .scoring import _patron

# Tecnologías sin ambigüedad ("go", "r" o "c" se excluyen a propósito: aparecen en cualquier texto).
TECNOLOGIAS = [
    "python", "sql", "dbt", "bigquery", "snowflake", "redshift", "databricks", "airflow", "spark",
    "kafka", "etl", "elt", "data warehouse", "data modeling", "postgresql", "postgres", "mysql",
    "mongodb", "redis", "elasticsearch", "supabase", "firebase", "docker", "kubernetes", "terraform",
    "aws", "azure", "gcp", "google cloud", "linux", "git", "github actions", "ci/cd",
    "react", "next.js", "node.js", "typescript", "javascript", "vue", "angular", "svelte", "tailwind",
    "express", "graphql", "rest api", "php", "laravel", "java", "spring", ".net", "c#", "golang",
    "rust", "ruby", "rails", "django", "flask", "fastapi", "flutter", "react native", "kotlin", "swift",
    "n8n", "zapier", "make.com", "power automate", "bitrix24", "hubspot", "salesforce", "airtable",
    "power bi", "tableau", "looker", "metabase", "excel", "pandas", "numpy", "scikit-learn", "xgboost",
    "tensorflow", "pytorch", "machine learning", "nlp", "llm", "rag", "openai", "langchain",
    "playwright", "selenium", "puppeteer", "beautifulsoup", "scraping", "chatbot", "discord",
    "whatsapp", "telegram", "shopify", "wordpress", "figma", "jira", "sap", "oracle",
]

_ANIOS = re.compile(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?|años)\b", re.I)


@dataclass
class Encaje:
    tenes: list[str] = field(default_factory=list)
    faltan: list[str] = field(default_factory=list)
    anios: int | None = None


def _texto_perfil(mem: Memory) -> str:
    partes = [mem.perfil_core(), mem.contexto_personal()]
    partes += [mem.modulo(m) for m in ("DATA", "WEB", "AUTOMATION", "BOTS", "SCRAPING")]
    return "\n".join(partes).lower()


def analizar(ticket: Ticket, mem: Memory) -> Encaje:
    texto, perfil = ticket.text, _texto_perfil(mem)
    enc = Encaje()
    for tec in TECNOLOGIAS:
        if _patron(tec, False).search(texto):
            (enc.tenes if _patron(tec, False).search(perfil) else enc.faltan).append(tec)
    pedidos = [int(n) for n in _ANIOS.findall(texto) if 0 < int(n) <= 20]
    enc.anios = max(pedidos) if pedidos else None
    return enc
