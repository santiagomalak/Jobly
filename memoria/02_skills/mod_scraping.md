---
id: mod_scraping
modulo: SCRAPING
version: 1
match_si_ticket_menciona: [scraping, scraper, crawler, beautifulsoup, playwright, selenium, data extraction, web scraping, lead generation, price monitoring, parse, crawl, puppeteer, captcha, proxy]
ticket_range_usd: [150, 400]
dias_entrega: [1, 3]
---

# MÓDULO SCRAPING & EXTRACCIÓN

## Pitch de una línea
"Extraigo datos de la web de forma estable: manejo paginación, cambios de layout, rate limits y entrego el dataset limpio en el formato que uses."

## Qué sé hacer
- **Estático:** requests + BeautifulSoup/lxml, sesiones, headers, manejo de cookies.
- **Dinámico:** Playwright y Selenium para SPA, scroll infinito, interacción con formularios, espera por selectores.
- **Robustez:** reintentos con backoff exponencial, rotación de user-agents, respeto de rate limits, checkpointing para reanudar.
- **Salida:** CSV, Excel, JSON, carga directa a Postgres/BigQuery/Google Sheets/Airtable.
- **Monitoreo:** correr en cron y alertar cuando el sitio cambia de estructura (el scraper no falla en silencio).

## Entregables estándar
1. Script parametrizable con CLI o archivo de config (nada hardcodeado).
2. Dataset de muestra validado antes de la corrida completa.
3. Documentación de los campos extraídos y sus limitaciones.
4. Manejo de errores + log de filas descartadas y por qué.

## Precios de referencia
| Trabajo | USD | Días |
|---|---|---|
| Scraper de un sitio estático, < 10k registros | 150–200 | 1 |
| Scraper de SPA con login / paginación compleja | 250–350 | 2 |
| Scraper + pipeline de carga + scheduling + alertas | 300–400 | 2–3 |
| Reparación de scraper roto | 100–180 | 0.5 |

## Preguntas de calificación
1. ¿Qué sitio(s) exactamente? (Los miro antes de cotizar — es no negociable.)
2. ¿Cuántos registros y cada cuánto hay que refrescar?
3. ¿Hay login o es público?
4. ¿Qué campos necesitás y para qué los vas a usar?

## Límites éticos y legales — filtro duro
- No scrapeo datos personales para spam masivo ni sitios que lo prohíben explícitamente en sus términos.
- No trabajo con evasión de CAPTCHA en sitios que lo prohíben, ni con credenciales robadas.
- Si el ticket huele a scraping de perfiles personales para venta de leads → descartar y no responder.

## Señales de alarma
- "Scrapear LinkedIn/Instagram a escala" → descartar (legal + técnico + reputación).
- Presupuesto < $80 por "solo una tablita" → descartar.
