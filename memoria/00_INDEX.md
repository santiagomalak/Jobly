---
id: index
version: 1
updated: 2026-09-21
---

# ÍNDICE DE MEMORIA — Santiago Aragón Malak

Este directorio es la **fuente de verdad** que consume el motor de evaluación del radar.
Regla de oro: **un archivo = un propósito**. El motor carga solo los módulos que hacen match
con el ticket entrante, nunca el CV completo.

| Archivo | Para qué se usa | Lo lee... |
|---|---|---|
| `01_perfil_core.md` | Identidad, tarifas, capacidad, idiomas, no-negociables | Siempre |
| `02_skills/mod_*.md` | Evidencia por stack. Un módulo = una venta completa | Solo el/los que matchean |
| `03_pocs_github.md` | Pruebas verificables (repo/demo) por módulo | Al redactar el pitch |
| `04_log_proyectos.md` | Historial: ticket → resultado → aprendizaje | Scoring + retros |
| `05_pricing_y_limites.md` | Tabla de precios por tipo de trabajo y piso de precio | Filtro + negociación |
| `06_plantillas_venta.md` | Plantillas de primer contacto y seguimiento | Generación de pitch |
| `07_objeciones.md` | Respuestas a objeciones frecuentes | Canal copiloto |
| `08_taxonomia_keywords.md` | Keywords → módulo. Es el "router" del scoring | Motor de scoring |

## Cómo se usa en el pipeline

1. Entra un ticket (RSS/API/scrape).
2. `08_taxonomia_keywords.md` decide **qué módulo** activar.
3. `05_pricing_y_limites.md` decide si el presupuesto pasa el filtro.
4. El LLM recibe: `01_perfil_core` + **solo el módulo ganador** + las PoCs de ese módulo.
5. Sale un pitch de 3 párrafos → Discord.

## Regla de mantenimiento
Después de CADA ticket (ganado o perdido): actualizar `04_log_proyectos.md`.
Después de cada proyecto entregado: agregar la PoC a `03_pocs_github.md`.
Memoria desactualizada = pitches genéricos = cero conversión.
