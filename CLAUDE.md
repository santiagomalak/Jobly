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

## Arquitectura

```
sources.py   → recolecta tickets: RSS / RemoteOK / Remotive / HN / Reddit / Google Sheet (CSV)
db.py        → SQLite local, o Turso (libSQL por HTTP) si hay TURSO_* — mismo SQL
store.py     → dedup por fingerprint, estados del pipeline, notas, métricas del KPI
scoring.py   → killers → módulo ganador → bonus/penalizaciones → ubicación → presupuesto → verdict
memory.py    → carga SOLO perfil core + el módulo que ganó (no el CV completo)
pitch.py     → arma el prompt y llama a llm.py
ask.py       → asistente de formularios: responde con perfil + contexto personal (09_*.md)
llm.py       → cascada Groq → OpenRouter :free → Ollama → plantilla sin IA
notify.py    → embed + propuesta en bloque de código al webhook de Discord
web.py       → CRM web (Flask): pipeline, detalle, preguntar, agregar/importar. Login obligatorio
main.py      → CLI: run / doctor / stats / marcar / pitch / ask / serve / test-discord
app.py       → entrypoint de Vercel (importa radar.web)
```

Dos procesos, una base: el **cron** (GitHub Actions, `radar run`) escribe tickets; el **CRM web**
(Vercel) los lee y cambia estados. Comparten Turso. Sin `TURSO_*` todo corre igual sobre SQLite
local (solo válido en tu PC: Vercel no persiste archivos).

Flujo del motor: `main.cmd_run()` orquesta todo. Empezá a leer ahí.

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
python -m radar.main ask "<pregunta>" --max-chars 300 [--oferta "<texto>"]   # respuesta para un formulario
python -m radar.main serve           # CRM web local (necesita JOBLY_PASSWORD en .env)
python scripts/selftest.py           # scoring + memoria + pitch (usa el LLM si hay claves)
python scripts/selftest_web.py       # web, Turso (mock), store. Sin internet. Corre en CI
python scripts/ingest_one.py --interactivo   # evaluar un ticket a mano
```

**Después de tocar `scoring.py`, `memory.py` o `pitch.py`, corré `scripts/selftest.py`.**
Tiene asserts de regresión: killers por subcadena (`$5` vs `$500`), keywords cortas (`rag` vs
`average`), sueldo anual vs presupuesto, ubicación, y que ninguna PoC ⬜ PENDIENTE llegue al prompt.
**Después de tocar `web.py`, `store.py` o `db.py`, corré `scripts/selftest_web.py`.**

---

## Convenciones del código

- Python 3.10+. Dependencias mínimas a propósito: `requests`, `feedparser`, `PyYAML`,
  `python-dotenv` y `flask` (solo para el CRM web). Turso se habla por HTTP con `requests`, sin
  driver. **No agregues dependencias sin una razón fuerte.**
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
- No inventar PoCs, proyectos ni cifras en los pitches ni en `ask`. `memory.pocs_de()` descarta
  las PoCs ⬜ PENDIENTE (antes llegaban al prompt y el LLM las citaba como trabajo hecho) y la
  única prueba citable son los "Proyectos reales verificables" de `09_contexto_personal.md`,
  filtrados por módulo. Un test del selftest lo cuida. Los niveles se copian textuales del CV.
- No agregar un "modo agresivo" que postule automáticamente. El sistema genera la propuesta;
  el envío lo decide Santiago. Es a propósito. Vale también para LinkedIn/Upwork/Workana: cero
  automatización de clicks o formularios en plataformas de terceros (ToS y baneo de cuenta).
- El CRM web nunca se expone sin login: sin `JOBLY_PASSWORD` no responde (`web.guardia`). No
  quites eso ni agregues rutas públicas salvo `/healthz`. Los `href` con URLs externas pasan por
  el filtro `safe_url`.
- Nada de cuentas falsas, VPN ni VMs para evadir bloqueos de plataformas. Si una fuente bloquea,
  se usa su API oficial o se descarta.
- No relajar los filtros éticos de `mod_scraping.md` ni los `killers` de scraping de datos
  personales.

---

## Estado actual y trabajo pendiente

**Funciona:** scoring (con límites de palabra), memoria modular, cascada de LLM, Discord, dedup,
CLI, CRM web con login (pipeline, detalle del ticket, asistente `ask`, carga manual e importación
de planillas), capa Turso, 2 workflows de n8n, CI de tests. Selftests verdes.

**Diagnóstico de fuentes (23/09/2026):** las fuentes públicas casi no traen micro-proyectos
freelance; lo que hay son puestos full-time Senior y avisos de marketplaces de talento. Por eso el
umbral se dejó en 48 (bajarlo solo trae ruido) y la vía más productiva es cargar ofertas propias
desde el CRM ("Agregar"). Fuentes por investigar: Workana, Freelancer.com, Torre.ai, Upwork API.

**Pendiente, por prioridad:**
0. Desplegar: `docs/DEPLOY.md` (Turso + Vercel + secrets). Requiere cuentas de Santiago.
1. ~~RSS de Upwork~~ — MUERTO. Upwork discontinuó RSS para job search el 20/08/2024 (confirmado
   en su Help Center). No hay URL que pegar, ninguna búsqueda guardada genera un link que
   funcione. El único camino que queda para Upwork es su Developer API oficial (OAuth, requiere
   registrar app y aprobación de Upwork) — no un scraper directo, ver la regla de "Qué NO hacer"
   más arriba sobre scraping/términos de servicio. Evaluar si vale la pena el esfuerzo de esa
   API o si conviene sumar otras fuentes con API/RSS pública en su lugar.
2. Las PoCs de `03_pocs_github.md` están todas en ⬜ PENDIENTE. La prioritaria es **A1**
   (`n8n-crm-whatsapp-bridge`): es la prueba que hoy le falta al párrafo 3 de cada pitch.
3. Revisar `memoria/09_contexto_personal.md` (borrador desde los CVs): sección "Para confirmar"
   (fechas de Ivolution, nivel de inglés, universidad de la diplomatura, motivación, salario fijo).
   Tres cambios de taxonomía del 23/09 esperan tu veto: killers `not your tech stack` y
   `application-only`, y penalizaciones `N+ years`.
4. ~~store.py tiene la columna estado pero nada la actualiza~~ — RESUELTO: comando
   `radar marcar <fingerprint> <estado>` implementado, escribe en `memoria/04_log_proyectos.md`.

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
