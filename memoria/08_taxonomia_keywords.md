---
id: taxonomia
version: 1
updated: 2026-09-21
carga: motor de scoring
---

# TAXONOMÍA DE KEYWORDS → MÓDULO

Este archivo es el **router** del scoring. Editalo cuando descubras un término nuevo que te trae
buenos tickets. Las keywords se comparan en minúsculas contra título + descripción del ticket.

## Pesos
- `strong` = +12 puntos cada una (máx. 3 contabilizadas por módulo)
- `weak` = +4 puntos cada una (máx. 3)
- `killer` = descarta el ticket completo sin importar el score

```yaml
modulos:
  AUTOMATION:
    strong: [n8n, zapier, make.com, integromat, workflow automation, api integration, webhook, bitrix24, crm integration, automate process, business process automation]
    weak: [automation, integrate, sync, crm, hubspot, airtable, google sheets, notion, api]
  DATA:
    strong: [dbt, bigquery, data pipeline, analytics engineer, data warehouse, etl pipeline, elt, power bi, metabase, looker studio, sql optimization]
    weak: [sql, dashboard, reporting, kpi, data cleaning, pandas, postgres, snowflake, visualization]
  WEB:
    strong: [react, next.js, node.js, express, typescript, supabase, full stack developer, rest api, mvp development]
    weak: [javascript, frontend, backend, crud, landing page, website, web app, tailwind, mongodb]
  SCRAPING:
    strong: [web scraping, scraper, playwright, selenium, beautifulsoup, crawler, data extraction, price monitoring]
    weak: [scrape, crawl, parse, extract data, puppeteer, proxy]
  BOTS:
    strong: [discord bot, telegram bot, slack bot, chatbot development, ai agent, llm integration, openai api, rag]
    weak: [bot, chatbot, automation bot, whatsapp, gpt, ai integration]

killers:
  # Descartan el ticket sin importar nada más
  - unpaid
  - equity only
  - revenue share
  - "no budget"
  - internship
  - "long term full time"
  - "full-time employee"
  - wordpress theme customization
  - "fix my wordpress"
  - mlm
  - forex signals
  - "crypto trading bot"
  - "sports betting bot"
  - "instagram followers"
  - "linkedin scraping at scale"
  - "bypass captcha"
  - "fake reviews"
  - "write my thesis"
  - "$5"
  - "$10/hour"
  - "health insurance"
  - "equity grant"
  - "401k"
  - "join our team"
  - "we're hiring"
  - "interview process"
  # Marketplaces de talento: listan 50 tecnologías en el mismo aviso y matchean todo
  - "not your tech stack"      # Lemon.io
  - "application-only"         # A.Team

bonus:
  # Suman puntos extra, transversales a los módulos
  "urgent": 6
  "asap": 5
  "quick": 4
  "small project": 5
  "one-time": 4
  "fix": 5
  "broken": 7
  "migrate": 4
  "portuguese": 8
  "brazil": 8
  "spanish": 6
  "latam": 6
  "argentina": 5
  "documentation included": 3

penalizaciones:
  "50+ proposals": -20
  "agency only": -25
  "must be us based": -40
  "us citizen": -40
  "on-site": -40
  "full time": -25
  "years of experience": -6
  "senior only": -8
  "team lead": -10
  "salary": -30
  # Años exigidos: tu experiencia comercial es de ~1 año, no compitas donde piden 4+
  "4+ years": -10
  "5+ years": -14
  "6+ years": -16
  "7+ years": -18
  "8+ years": -20
  "10+ years": -25
```

## Cómo mejorar esto con el tiempo
Cada domingo, mirá `04_log_proyectos.md`:
- Ticket **ganado** cuyo término no estaba acá → agregarlo a `strong` del módulo.
- Ticket que pasó el filtro y era basura → agregar su término a `killers` o `penalizaciones`.
Tres iteraciones y el radar deja de traerte ruido.
