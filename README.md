# radar-freelance

Sistema de prospección autónoma: monitorea feeds de proyectos freelance, los puntúa contra
un sistema de memoria modular en `.md`, redacta la propuesta comercial y te la deja lista
para copiar en Discord.

**Objetivo operativo:** piso de USD 900/mes con tickets de 1–3 días (USD 150–450).

```
FUENTES          MOTOR                      SALIDA
─────────        ──────────────────         ─────────────────
Upwork RSS   ┐   dedup (sqlite)             #02-propuestas-listas
RemoteOK     ├─► scoring vs memoria/  ──►   ticket + pitch de 3 párrafos
Reddit       │   LLM en cascada (gratis)    listo para copiar y pegar
WWR / HN     ┘   pitch de 3 párrafos
```

---

## Instalación (10 minutos)

```bash
cd radar-freelance
pip install -r requirements.txt
copy .env.example .env        # en Linux/Mac: cp .env.example .env
```

Editá `.env` con:
1. **Webhooks de Discord** — creá el servidor siguiendo `docs/FASE2_discord.md`.
2. **API key de Groq** (gratis, 30 segundos): https://console.groq.com/keys

Verificá todo:

```bash
python -m radar.main doctor          # diagnostica memoria, fuentes, LLMs y webhooks
python -m radar.main test-discord    # tiene que llegarte un mensaje
python scripts/selftest.py           # prueba scoring y pitch sin internet
```

Primera corrida real, sin enviar nada:

```bash
python -m radar.main run --dry
```

Cuando la calidad te convenza:

```bash
python -m radar.main run
```

---

## Comandos

| Comando | Qué hace |
|---|---|
| `python -m radar.main run` | Corrida completa: recolecta, puntúa, redacta y notifica |
| `python -m radar.main run --dry` | Igual pero imprime en consola, no toca Discord |
| `python -m radar.main doctor` | Diagnóstico de configuración |
| `python -m radar.main stats` | Métricas acumuladas |
| `python -m radar.main test-discord` | Prueba el webhook |
| `python scripts/selftest.py` | Prueba el motor con tickets de ejemplo (sin internet) |
| `python scripts/ingest_one.py --interactivo` | Evalúa un ticket que viste a mano y genera el pitch |

---

## Estructura

```
radar-freelance/
├── memoria/                    ← FASE 1: la fuente de verdad. Editá esto seguido.
│   ├── 00_INDEX.md
│   ├── 01_perfil_core.md           siempre se carga
│   ├── 02_skills/mod_*.md          5 módulos independientes (se carga SOLO el que matchea)
│   ├── 03_pocs_github.md           pruebas verificables por módulo
│   ├── 04_log_proyectos.md         ← actualizá después de CADA postulación
│   ├── 05_pricing_y_limites.md
│   ├── 06_plantillas_venta.md
│   ├── 07_objeciones.md
│   └── 08_taxonomia_keywords.md    ← el router del scoring. Editalo cada domingo.
├── radar/                      ← FASE 2: el motor
│   ├── sources.py                  RSS / RemoteOK / Reddit / HN
│   ├── scoring.py                  killers, módulos, bonus, presupuesto
│   ├── memory.py                   carga modular de la memoria
│   ├── llm.py                      cascada Groq → OpenRouter → Ollama → plantilla
│   ├── pitch.py                    generación del pitch de 3 párrafos
│   ├── notify.py                   embeds de Discord
│   ├── store.py                    dedup y persistencia (sqlite)
│   └── main.py                     CLI
├── prompts/                    ← FASE 3: copiloto de ventas
├── n8n/                            workflows para importar
├── docs/                       ← FASE 2 (Discord) y FASE 4 (roadmap)
├── config.yaml                     umbrales
└── sources.yaml                    qué feeds mirar
```

---

## El punto clave: memoria modular

Si entra un ticket que solo pide **n8n**, el LLM recibe únicamente
`01_perfil_core.md` + `mod_automation_n8n.md` + las PoCs de ese módulo.
**Nunca ve dbt, React ni ciberseguridad.**

Esto importa porque un pitch que lista todo tu stack le dice al cliente "soy generalista,
probablemente mediocre en lo tuyo". Un pitch que habla solo de n8n le dice "esto es lo que hago".

---

## La cascada de LLM (gratis, escalable, nunca falla)

| Nivel | Proveedor | Costo | Cuándo entra |
|---|---|---|---|
| 1 | Groq (`llama-3.3-70b`) | gratis | siempre que haya `GROQ_API_KEY` |
| 2 | OpenRouter modelos `:free` | gratis | si Groq falla o llegó al rate limit |
| 3 | Ollama local | gratis | si no hay internet o los anteriores caen |
| 4 | **Plantilla sin IA** | gratis | último recurso — siempre funciona |

El nivel 4 es el que hace que el sistema "funcione siempre": aunque se caiga todo,
la alerta llega con una propuesta usable y vos la refinás en `#03-copiloto-chat`.

Para subir la calidad en un ticket importante: copiás el pitch al canal copiloto y usás
`prompts/copiloto_respuesta_cliente.md` con Claude. **Lo automático es para el volumen;
lo manual es para los tickets de $400.**

---

## Automatizarlo con n8n

1. n8n → Import from File → `n8n/radar_scheduler.json`
2. Editá el nodo **Correr radar**: ajustá la ruta al proyecto.
3. Si tu n8n corre en Docker, el nodo Execute Command no ve tu Python del host: usá el
   Windows Task Scheduler (`schtasks`) o cron para el `run`, y dejá n8n solo para las alertas.
4. Activá el workflow. Cada 2 h corre solo y avisa a `#09-errores` si algo falla.

También hay `n8n/radar_webhook_ingest.json`: expone un webhook para empujar a mano un ticket
que viste en Twitter o en un grupo, y que pase por el mismo motor.

---

## Ajuste continuo

| Síntoma | Qué tocar |
|---|---|
| Llegan menos de 3 alertas por día | Bajar `min_score`, habilitar más fuentes |
| Llega ruido | Subir `min_score`, agregar términos a `killers` |
| El pitch suena a IA | Editar las reglas en `radar/pitch.py` y `prompts/pitch_system.md` |
| Nadie responde | El párrafo 1 está hablando de vos, no de su problema |
| Responden pero no cierran | Revisar `memoria/07_objeciones.md` y el precio |

**Cada domingo, 20 minutos:** pegás `04_log_proyectos.md` en el prompt de
`prompts/copiloto_postmortem.md` y aplicás los 3 ajustes que te devuelva.

---

## Trabajar el proyecto con Claude Code

`CLAUDE.md` en la raíz es la memoria del proyecto: arquitectura, convenciones, lo que no hay que
hacer y el pendiente. Claude Code lo lee solo al iniciar.

```bash
cd radar-freelance
claude
```

Comandos propios ya incluidos en `.claude/commands/`:

| Comando | Para qué |
|---|---|
| `/postular <url o título>` | Evalúa un ticket a mano y devuelve la propuesta lista |
| `/copiloto <mensaje del cliente>` | Arma la respuesta en una negociación abierta |
| `/retro` | Retro semanal: analiza el log y propone ajustes al radar |
| `/diagnostico` | Cuando el radar no trae lo que debería |

Prompt de arranque para sesiones sin `CLAUDE.md` cargado: `docs/PROMPT_BOOTSTRAP.md`.

---

## Aviso legal y ético
El scraping se limita a feeds públicos y APIs abiertas, respetando rate limits.
El módulo de scraping incluye un filtro explícito: nada de datos personales para spam,
nada de sitios que lo prohíben, nada de evasión de CAPTCHA. Un ticket que pide eso
se descarta automáticamente vía `killers`.
