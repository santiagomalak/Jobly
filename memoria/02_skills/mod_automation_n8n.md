---
id: mod_automation_n8n
modulo: AUTOMATION
version: 1
match_si_ticket_menciona: [n8n, make, zapier, automation, workflow, integración, api integration, webhook, crm, bitrix, hubspot, airtable, notion sync, google sheets automation, whatsapp bot, zap]
ticket_range_usd: [150, 450]
dias_entrega: [1, 3]
---

# MÓDULO AUTOMATION / n8n

> Este módulo se vende SOLO. Si el ticket es "necesito conectar mi CRM con WhatsApp",
> el pitch usa únicamente este archivo. Nunca mencionar dbt, React ni pentesting.

## Pitch de una línea
"Construyo automatizaciones en n8n que conectan tus herramientas y corren solas, con logs y reintentos — no scripts que se rompen el martes."

## Qué sé hacer (afirmaciones verificables)
- Diseño y despliegue de workflows n8n: triggers (cron, webhook, polling), branching, error workflows, reintentos con backoff.
- Integración vía REST/GraphQL con autenticación OAuth2, API key y HMAC en webhooks.
- Make.com y Zapier cuando el cliente ya está casado con esa plataforma.
- CRM: Bitrix24 (entidades, deals, actividades, webhooks entrantes/salientes), HubSpot básico.
- Nodos Code (JavaScript/Python) para transformaciones que los nodos nativos no cubren.
- Self-hosting de n8n con Docker + persistencia + variables de entorno.

## Entregables estándar de este módulo
1. Workflow(s) exportados en JSON, versionados en repo.
2. Documento de credenciales requeridas (sin secretos, solo el mapa).
3. Error workflow que notifica a Slack/Discord/email cuando algo falla.
4. Video Loom de 3–5 min explicando el funcionamiento y cómo modificarlo.
5. 7 días de soporte post-entrega para ajustes de mapeo de campos.

## Precios de referencia
| Trabajo | USD | Días |
|---|---|---|
| Workflow simple (2 apps, 1 trigger) | 150–200 | 1 |
| Workflow con lógica de negocio (3–5 apps, branching, dedup) | 250–350 | 2 |
| Integración CRM completa + panel de estado | 350–450 | 3 |
| Fix/rescate de automatización rota ajena | 120–180 | 0.5–1 |

## Preguntas de calificación (hacer SIEMPRE antes de cotizar)
1. ¿Qué herramientas exactamente y tenés las cuentas con permisos de admin?
2. ¿Volumen: cuántos registros por día?
3. ¿n8n lo tenés self-hosted o cloud? ¿Versión?
4. ¿Qué pasa hoy cuando el proceso falla — quién se entera?

## Señales de alarma en el ticket
- "Necesito automatizar todo mi negocio" sin proceso definido → pedir 1 proceso concreto o descartar.
- Presupuesto < $100 con 5 integraciones → descartar.
- Pide acceso a producción antes del contrato → descartar.
