---
description: Diagnostica por qué el radar no está trayendo lo que debería
---

Algo anda mal con el radar. Diagnosticá en este orden y no saltees pasos:

1. `python -m radar.main doctor` — leé toda la salida.
2. `python scripts/selftest.py` — si falla, el problema está en el motor, no en las fuentes.
3. `python -m radar.main run --dry` — mirá cuántos tickets brutos entran por fuente.
4. `python -m radar.main stats`

Después usá esta tabla para el diagnóstico:

| Síntoma | Causa probable | Dónde tocar |
|---|---|---|
| 0 tickets brutos | fuentes caídas o bloqueadas | `sources.yaml`, logs de `sources.collect()` |
| Muchos brutos, 0 pasan | `min_score` muy alto o taxonomía pobre | `config.yaml`, `08_taxonomia_keywords.md` |
| Pasa basura | faltan `killers` | `08_taxonomia_keywords.md` |
| Pitch genérico | el módulo no matchea bien, o el LLM cayó a plantilla | mirá `pitch_engine` en la alerta |
| No llega a Discord | webhook mal o rate limit | `doctor` + `test-discord` |
| Todo cae a plantilla | las API keys no están o expiraron | `.env`, `llm.available()` |

Decime qué encontraste y proponé el arreglo antes de aplicarlo. Si el arreglo es una línea de
YAML en la memoria, preferí eso antes que tocar código.
