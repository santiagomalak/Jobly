---
id: mod_data_pipelines
modulo: DATA
version: 1
match_si_ticket_menciona: [dbt, bigquery, sql, etl, elt, data pipeline, data warehouse, analytics engineer, metabase, looker studio, power bi, dashboard, kpi, data cleaning, snowflake, postgres analytics, reporting]
ticket_range_usd: [200, 450]
dias_entrega: [2, 4]
---

# MÓDULO DATA PIPELINES & ANALYTICS

> Se vende solo. Si el ticket es "necesito un dashboard de ventas", este archivo es todo el CV.

## Pitch de una línea
"Convierto datos sucios y dispersos en un modelo confiable y un dashboard que el equipo realmente usa — con tests que avisan cuando un número se rompe."

## Qué sé hacer
- **SQL avanzado:** window functions, CTEs recursivas, optimización de queries, particionado y clustering en BigQuery.
- **dbt:** modelos staging/intermediate/marts, tests (unique, not_null, relationships, custom), snapshots para SCD2, documentación y lineage, macros y Jinja.
- **BigQuery:** ingestión, scheduled queries, control de costo por slot/bytes escaneados.
- **Python de datos:** pandas para limpieza y reconciliación, validación de esquemas, cargas incrementales.
- **Visualización:** Power BI (modelo tabular, DAX), Metabase, Looker Studio, Streamlit para apps internas.
- **Orquestación:** cron + n8n, o Airflow básico.

## Entregables estándar
1. Repo dbt (o SQL versionado) con modelos, tests y `dbt docs`.
2. Diccionario de métricas: definición exacta de cada KPI, acordada con el cliente por escrito.
3. Dashboard con máximo 6 métricas por vista (más es ruido).
4. Chequeos de frescura y calidad que alertan a Discord/email.
5. Handoff documentado: cómo agregar una métrica nueva sin mí.

## Precios de referencia
| Trabajo | USD | Días |
|---|---|---|
| Limpieza + modelado de un dataset y dashboard de 1 vista | 200–280 | 2 |
| Pipeline dbt (5–10 modelos) + tests + docs | 300–420 | 3 |
| Auditoría de warehouse existente + plan de optimización de costos | 180–250 | 1–2 |
| Dashboard Power BI / Metabase sobre datos ya modelados | 150–220 | 1–2 |

## Preguntas de calificación
1. ¿Dónde viven los datos hoy y quién tiene acceso? ¿Puedo tener un dump de muestra?
2. ¿Cuál es LA pregunta de negocio que el dashboard tiene que responder?
3. ¿Quién es el consumidor final y con qué frecuencia mira?
4. ¿Hay una definición previa de las métricas o la construimos?

## Señales de alarma
- "Los datos están en varios Excel que cada área maneja distinto" y presupuesto < $200 → el 70% del trabajo es reconciliación. Cotizar alto o descartar.
- Piden migración de warehouse completo por $300 → descartar.
