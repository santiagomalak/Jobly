# CLAUDE.md — Jobly (radar-freelance)

Memoria de proyecto para Claude Code. Leé esto antes de tocar nada.

`Jobly` es el nombre del proyecto/repo. `radar-freelance` sigue siendo la descripción de qué
hace. El paquete Python se sigue llamando `radar/` (`python -m radar.main ...`) — no se
renombró para no romper todo lo demás; es puramente cosmético en README/CLAUDE.md por ahora.

---

## Qué es este proyecto

Sistema de prospección freelance autónoma. Monitorea feeds de proyectos, los puntúa contra un
sistema de memoria modular en `.md`, redacta la propuesta comercial con un LLM y la deja lista
para copiar en Discord.

**Dueño:** Santiago Aragón Malak — ingeniero de automatización y datos, Córdoba (AR), UTC-3.
**Objetivo de negocio:** piso de USD 900/mes con tickets de 1–3 días (USD 150–450).
**KPI que define si el sistema sirve:** 5 propuestas enviadas y 1 cierre por semana.

Este no es un proyecto de software por el software. **Todo cambio se juzga por si aumenta
propuestas enviadas o tasa de cierre.** Refactors que no mueven ese número son ruido.

---

## Arquitectura en 6 líneas

```
sources.py   → recolecta tickets de RSS / RemoteOK / Reddit / HN
store.py     → deduplica por fingerprint (sha256 de título normalizado + url) en SQLite
scoring.py   → killers → módulo ganador → bonus/penalizaciones → presupuesto → verdict
memory.py    → carga SOLO perfil core + el módulo que ganó (no el CV completo)
pitch.py     → arma el prompt y llama a llm.py
llm.py       → cascada Groq → OpenRouter :free → Ollama → plantilla sin IA
notify.py    → embed + propuesta en bloque de código al webhook de Discord
main.py      → CLI: run / run --dry / doctor / stats / test-discord
```

Flujo completo: `main.cmd_run()` es el único lugar donde se orquesta todo. Empezá a leer ahí.

---

## La decisión de diseño central: memoria modular

`memoria/` es **la fuente de verdad del negocio**, no documentación. El código la lee en runtime.

Si entra un ticket que solo pide n8n, el LLM recibe únicamente:
`01_perfil_core.md` + `02_skills/mod_automation_n8n.md` + la sección AUTOMATION de `03_pocs_github.md`.

**Nunca ve dbt, React ni ciberseguridad.** Eso es deliberado: un pitch que lista todo el stack le
dice al cliente "soy generalista"; uno que habla solo de n8n le dice "esto es lo que hago".

Si alguna vez te tienta pasarle toda la memoria al LLM "para que tenga más contexto": no. Rompe
la propuesta de valor del sistema.

`08_taxonomia_keywords.md` es el router. Contiene un bloque ```yaml que `memory.taxonomia()`
parsea. **Editar ese archivo cambia el comportamiento del scoring sin tocar código** — así está
pensado. Santiago lo ajusta los domingos con los datos de `04_log_proyectos.md`.

---

## Comandos

```bash
python -m radar.main doctor          # SIEMPRE correr esto primero al diagnosticar algo
python -m radar.main run --dry       # corrida sin tocar Discord, imprime en consola
python -m radar.main run             # corrida real
python -m radar.main stats
python -m radar.main test-discord
python -m radar.main pitch <url>              # regenera el pitch de un ticket guardado
python -m radar.main marcar <fingerprint> <estado>  # nuevo|postulado|respondido|ganado|perdido
                                               # también agrega la entrada en memoria/04_log_proyectos.md
python scripts/selftest.py           # motor con fixtures, sin internet. Es el test suite.
python scripts/ingest_one.py --interactivo   # evaluar un ticket a mano
```

**Después de tocar `scoring.py`, `memory.py` o `pitch.py`, corré `scripts/selftest.py`.**
Tiene asserts: verifica que al menos un fixture pase y que los killers filtren.

---

## Convenciones del código

- Python 3.10+. Sin framework. Dependencias mínimas a propósito: `requests`, `feedparser`,
  `PyYAML`, `python-dotenv`. **No agregues dependencias sin una razón fuerte.**
- Todo en español en docstrings, comentarios y strings de usuario. Los nombres de símbolos en
  inglés o español según ya esté — no unificar por unificar.
- `from __future__ import annotations` en todos los módulos.
- **Una fuente que falla no puede tumbar la corrida.** `sources.collect()` captura por fuente y
  sigue. Si agregás una fuente, respetá eso.
- **El LLM que falla no puede tumbar la corrida.** `llm.generate()` siempre devuelve algo; el
  nivel 4 (plantilla) no tiene red. Si tocás esa cascada, mantené esa garantía.
- Secretos solo en `.env` (gitignoreado). Nunca hardcodear webhooks ni API keys, ni siquiera en
  ejemplos de docstrings.
- Discord: 2 mensajes por ticket, tope `max_tickets_per_run`. `notify.post()` maneja 429 con
  espera. No subas el tope arriba de 20.

## Qué NO hacer

- No reescribir `memoria/*.md` por iniciativa propia. Ese contenido es de Santiago: son sus
  precios, sus límites y sus afirmaciones sobre lo que sabe hacer. Proponé, no edites solo.
- No inventar PoCs ni links de GitHub en los pitches. Si un módulo no tiene PoC publicada, el
  pitch describe el proyecto análogo sin link. Ya está manejado en `pitch.py`.
- No agregar un "modo agresivo" que postule automáticamente. El sistema genera la propuesta;
  el envío lo decide Santiago. Es a propósito.
- No relajar los filtros éticos de `mod_scraping.md` ni los `killers` de scraping de datos
  personales.

---

## Estado actual y trabajo pendiente

**Funciona:** scoring, memoria modular, cascada de LLM, notificación a Discord, dedup,
CLI completo, selftest verde, 2 workflows de n8n.

**Pendiente, por prioridad:**
1. Los RSS de Upwork en `sources.yaml` están en `enabled: false` — son personales, Santiago los
   tiene que generar desde búsquedas guardadas y pegarlos.
2. Las PoCs de `03_pocs_github.md` están todas en ⬜ PENDIENTE. La prioritaria es **A1**
   (`n8n-crm-whatsapp-bridge`): es la prueba que hoy le falta al párrafo 3 de cada pitch.
3. Los umbrales de `config.yaml` (`min_score: 48`) son una apuesta inicial sin datos. Hay que
   calibrarlos con las primeras corridas reales.
4. No hay scraping directo de Upwork/Freelancer más allá de RSS — a propósito, por términos de
   servicio. Si se agrega algo, que sea vía API oficial.
5. `store.py` tiene la columna `estado` (nuevo/postulado/respondido/ganado/perdido) pero nada la
   actualiza todavía. Candidato natural: un comando `radar marcar <fingerprint> <estado>` que
   además escriba la entrada en `memoria/04_log_proyectos.md`.

---

## Contexto sobre Santiago (para no proponerle cosas que no le sirven)

- Perfil técnico real: Python/pandas/scikit-learn, dbt/BigQuery/SQL, Node/React/TypeScript,
  Power BI, n8n/Make/Zapier/Bitrix24, Playwright/Selenium, ciberseguridad.
- Idiomas: español nativo, portugués C1 (ventaja comercial real con Brasil), inglés intermedio.
- Trabaja solo, ~6 h productivas por día, máximo 2 tickets en paralelo.
- Prefiere soluciones que **funcionen siempre** antes que soluciones elegantes: por eso la
  cascada de LLM termina en una plantilla sin IA.
- El presupuesto de infraestructura es ~USD 35/mes. **No propongas nada que agregue costo fijo
  sin decir explícitamente cuánto cuesta y qué reemplaza.**

---

## Cómo trabajar acá

1. Antes de cambiar comportamiento del scoring, leé `memoria/08_taxonomia_keywords.md` — puede
   que el cambio sea una línea de YAML y no código.
2. Antes de cambiar el tono de los pitches, leé `memoria/06_plantillas_venta.md` y
   `prompts/pitch_system.md`. Las reglas del prompt viven duplicadas en `radar/pitch.py`
   (constante `SYSTEM`) y en `prompts/pitch_system.md` — **si cambiás una, cambiá la otra.**
3. Cambios grandes: proponé el plan antes de escribir. Este sistema tiene que seguir funcionando
   todos los días mientras se lo modifica.
4. Si algo falla en producción, el primer paso es `python -m radar.main doctor`.
