# FASE 4 — Hoja de ruta: de cero a la primera propuesta hoy

> Principio: **el radar no genera plata, las propuestas sí.** Por eso el día 1 es 50% montaje
> y 50% postulación manual. No esperes a tener el sistema perfecto para empezar a vender.

---

## DÍA 1 — HOY (4 h de montaje + 2 h de caza manual)

### Bloque A — Montaje (90 min)
| # | Tarea | Tiempo |
|---|---|---|
| 1 | Crear el servidor de Discord con los 10 canales de `docs/FASE2_discord.md` | 15 min |
| 2 | Generar 3 webhooks (#01, #02, #09) y pegarlos en `.env` | 10 min |
| 3 | `pip install -r requirements.txt` y `python -m radar.main doctor` | 10 min |
| 4 | Sacar API key gratis de Groq (console.groq.com/keys) → `.env` | 10 min |
| 5 | `python -m radar.main test-discord` → tiene que llegar el mensaje | 5 min |
| 6 | `python scripts/selftest.py` → verifica scoring y pitch sin internet | 5 min |
| 7 | `python -m radar.main run --dry` → primera corrida real, revisás la calidad | 20 min |
| 8 | Ajustar `min_score` en `config.yaml` según lo que viste | 15 min |

### Bloque B — Personalizar la memoria (60 min)
| # | Tarea |
|---|---|
| 9 | Releer `memoria/01_perfil_core.md` y corregir lo que no te represente |
| 10 | Revisar los 5 módulos: borrá lo que no sepas hacer **de verdad**. Un módulo mentiroso quema un cliente |
| 11 | Ajustar precios en `05_pricing_y_limites.md` a lo que estés dispuesto a cobrar hoy |

### Bloque C — Caza manual (2 h) ← **ESTO ES LO QUE TRAE PLATA HOY**
| # | Tarea |
|---|---|
| 12 | Crear/actualizar perfil de Upwork con el posicionamiento del perfil core (no "full stack junior") |
| 13 | Entrar a r/forhire y r/jobbit, filtrar `[HIRING]`, buscar n8n / scraping / automation |
| 14 | **Postular a 5 tickets hoy**, usando `scripts/ingest_one.py --interactivo` para generar cada pitch |
| 15 | Anotar las 5 en #04-postuladas y en `04_log_proyectos.md` |

**Meta del día 1: 5 propuestas enviadas.** Sin esto, el resto no importa.

---

## DÍA 2 — Automatizar y duplicar
- Importar `n8n/radar_scheduler.json` en tu n8n y ajustar la ruta del proyecto.
- Activarlo cada 2 h. Verificar que la primera corrida automática llegue a #02.
- Conseguir los RSS de Upwork: crear 3 búsquedas guardadas (n8n, web scraping, dbt/BigQuery),
  copiar los RSS a `sources.yaml` y poner `enabled: true`.
- **Postular a 5 tickets más.** Ahora con las alertas llegando solas.
- Responder los mensajes del día 1 usando `prompts/copiloto_respuesta_cliente.md`.

## DÍA 3 — Primera PoC y primer cierre
- Construir la PoC **A1** (`n8n-crm-whatsapp-bridge`) — 2-3 h. Con README y GIF.
  Es la que más tickets te va a habilitar y es la prueba que falta en el párrafo 3 del pitch.
- Linkearla en `memoria/03_pocs_github.md` — el radar la empieza a usar automáticamente.
- **Postular a 5 más.** Seguimiento 1 a las del día 1 que no respondieron.
- Para este punto deberías tener 1–3 conversaciones abiertas. Ahí se cierra.

## DÍA 4 — Negociar y entregar
- Usar `prompts/copiloto_arquitectura.md` para las conversaciones que pidan "¿cómo lo harías?".
- Cerrar el primer ticket. Adelanto si es > $250.
- **Empezar a construir apenas cobrás el adelanto.** Entregá el primer resultado visible en 24 h:
  es lo que convierte un cliente de $200 en un cliente recurrente.

## DÍA 5 — Consolidar
- Entregar. Video de 5 min + documentación. Pedir la reseña en el momento de entregar, no después.
- Preguntar: *"¿hay algo más del mismo estilo que te esté molestando?"* — el segundo ticket del
  mismo cliente es el más barato de conseguir que vas a tener.
- Actualizar `04_log_proyectos.md` y correr el prompt de postmortem.
- Ajustar keywords con lo aprendido.

---

## Ritmo de crucero (a partir de la semana 2)

| Momento | Duración | Qué hacés |
|---|---|---|
| 09:00 | 20 min | Revisar #02, postular a todo lo que tenga score ≥ 65 |
| 13:00 | 15 min | Segunda pasada + responder clientes |
| 19:00 | 20 min | Tercera pasada + seguimientos pendientes |
| Domingo | 30 min | Retro con `prompts/copiloto_postmortem.md`, ajustar taxonomía |

**KPI semanal: 5 propuestas enviadas, 1 cierre.** Con 20% de conversión y ticket promedio
de $250, eso son ~$1.000/mes. El objetivo de $900 se cumple con margen.

## Qué medir para saber si el sistema funciona
| Métrica | Si está mal | Qué tocar |
|---|---|---|
| Alertas por día | < 3 | Bajar `min_score`, habilitar más fuentes |
| Alertas por día | > 15 | Subir `min_score`, agregar killers |
| Tasa de respuesta | < 15% | El pitch. Revisá el párrafo 1: ¿habla de su problema o del tuyo? |
| Respuesta → cierre | < 30% | El precio o el manejo de objeciones. Revisá `07_objeciones.md` |
| Cierre → recurrencia | < 20% | La entrega. Falta documentación o el video de handoff |
