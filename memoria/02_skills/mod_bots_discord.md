---
id: mod_bots_discord
modulo: BOTS
version: 1
match_si_ticket_menciona: [discord bot, telegram bot, slack bot, chatbot, bot, whatsapp bot, openai integration, llm integration, rag, ai agent, automation bot, moderation bot]
ticket_range_usd: [150, 400]
dias_entrega: [1, 3]
---

# MÓDULO BOTS & CAPA LLM

## Pitch de una línea
"Armo bots de Discord/Telegram/Slack que hacen trabajo real: consultan datos, disparan procesos y responden con contexto — no un eco con IA."

## Qué sé hacer
- **Discord:** discord.py / discord.js, slash commands, embeds, botones y modales, roles y permisos, webhooks.
- **Telegram:** python-telegram-bot, teclados inline, manejo de estados de conversación.
- **Slack:** Bolt, slash commands, Block Kit.
- **Capa LLM:** integración con APIs de OpenAI/Anthropic/Groq/OpenRouter, control de costo, prompts versionados, fallback entre proveedores, RAG simple sobre documentos del cliente.
- **Conexión con el negocio:** el bot consulta una DB, dispara un workflow n8n o llama una API interna.
- **Deploy:** contenedor en Railway/Fly/VPS con reinicio automático.

## Entregables estándar
1. Bot desplegado y corriendo, con el token en variables de entorno del cliente (nunca en el repo).
2. Lista de comandos documentada.
3. Log de uso y manejo de errores visible.
4. Límites de gasto si usa LLM de pago.

## Precios de referencia
| Trabajo | USD | Días |
|---|---|---|
| Bot con 3–5 comandos sobre una API existente | 150–250 | 1 |
| Bot con capa LLM + contexto de documentos | 280–380 | 2 |
| Bot + panel de administración + métricas de uso | 350–400 | 3 |

## Preguntas de calificación
1. ¿Qué tiene que poder hacer un usuario, en 3 frases?
2. ¿Dónde vive el dato que el bot consulta?
3. ¿Quién paga el consumo de la API del LLM?
4. ¿Dónde se despliega y quién administra el servidor?

## Señales de alarma
- Bot para automatizar interacciones que violan los términos de la plataforma → descartar.
- "Un ChatGPT entrenado con mis datos" por $100 → educar sobre RAG vs fine-tuning o descartar.
