---
id: pocs
version: 1
updated: 2026-09-21
carga: al redactar pitch, filtrado por modulo
---

# PRUEBAS VERIFICABLES (PoCs)

> Regla: **cada módulo necesita mínimo 2 PoCs públicas con README y demo.**
> Una PoC sin README no sirve: el cliente no lee código, lee el README y mira el GIF.
> En el pitch se inserta UNA sola PoC: la del módulo que matchea. Nunca una lista.

## Formato obligatorio de cada PoC
```
repo-name/
├── README.md        <- Problema → solución → cómo correrlo → GIF/captura
├── demo.gif         <- 10-20 seg mostrando que funciona
└── src/
```
El README arranca con: "**Problema:** ... **Solución:** ... **Resultado:** ...". Sin biografía.

---

## MÓDULO AUTOMATION
| # | Nombre | Estado | URL | Frase para el pitch |
|---|---|---|---|---|
| A1 | `n8n-crm-whatsapp-bridge` | ⬜ PENDIENTE | | "Un workflow que sincroniza leads entrantes con el CRM y avisa por WhatsApp, con reintentos y error workflow." |
| A2 | `n8n-error-handling-kit` | ⬜ PENDIENTE | | "Plantilla de manejo de errores para n8n: captura, reintento con backoff y alerta a Discord." |

## MÓDULO DATA
| # | Nombre | Estado | URL | Frase para el pitch |
|---|---|---|---|---|
| D1 | `dbt-ecommerce-starter` | ⬜ PENDIENTE | | "Proyecto dbt de ejemplo: staging → marts, 12 tests y docs con lineage." |
| D2 | `sales-dashboard-streamlit` | ⬜ PENDIENTE | | "Dashboard de ventas con chequeos de frescura que avisan si el dato se rompe." |

## MÓDULO WEB
| # | Nombre | Estado | URL | Frase para el pitch |
|---|---|---|---|---|
| W1 | `crud-supabase-react-auth` | ⬜ PENDIENTE | | "CRUD con auth y roles desplegado, listo para clonar en 10 minutos." |
| W2 | `express-api-boilerplate` | ⬜ PENDIENTE | | "API Express con validación, manejo de errores y rate limiting." |

## MÓDULO SCRAPING
| # | Nombre | Estado | URL | Frase para el pitch |
|---|---|---|---|---|
| S1 | `resilient-scraper-template` | ⬜ PENDIENTE | | "Scraper con checkpointing: si se cae en la fila 8.000, retoma ahí." |
| S2 | `price-monitor-alerts` | ⬜ PENDIENTE | | "Monitor de precios que corre en cron y alerta cuando el layout del sitio cambia." |

## MÓDULO BOTS
| # | Nombre | Estado | URL | Frase para el pitch |
|---|---|---|---|---|
| B1 | `radar-freelance` (ESTE sistema) | 🟡 EN CURSO | | "Un bot que monitorea feeds de proyectos, los puntúa contra mi perfil y redacta la propuesta. Lo uso todos los días." |
| B2 | `telegram-db-query-bot` | ⬜ PENDIENTE | | "Bot de Telegram que consulta una base y devuelve reportes bajo demanda." |

---
## Prioridad de construcción (2–3 h cada una, en huecos entre tickets)
1. **A1** y **S1** — son los módulos con más volumen de tickets baratos y rápidos.
2. **B1** — ya lo estás construyendo: publicalo, es el mejor storytelling que tenés.
3. El resto, a medida que entren proyectos reales: **todo proyecto entregado se convierte en PoC anonimizada.**
