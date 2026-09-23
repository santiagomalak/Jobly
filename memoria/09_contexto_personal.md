---
id: contexto_personal
version: 0
updated: 2026-09-23
carga: comando `ask` (siempre) y bloque "proyectos reales" del pitch
---

# CONTEXTO PERSONAL — fuente única para el asistente

> BORRADOR armado desde `santiago-data/` (CV v3.0 + CV completo). Revisalo y corregilo:
> acá manda lo que vos confirmes. A propósito NO incluye DNI ni teléfono: este archivo viaja
> como contexto a proveedores de LLM (Groq / OpenRouter).
> Regla del asistente: solo afirma lo que está escrito acá o en el resto de `memoria/`.
> Lo que falta lo marca como `[COMPLETAR: ...]`, no lo inventa.

## Resumen profesional
Analytics Engineer / Data Scientist con experiencia real en producción. En Ivolution Sport
Science construí el sistema de monitoreo de rendimiento para 967 atletas en 13 deportes
(BigQuery, dbt, Metabase), que sigue siendo la herramienta de referencia de la organización
después de mi salida. Perfil híbrido Data + Full-Stack: puedo construir tanto el análisis como
la interfaz que lo presenta. Portugués C1, disponible para roles con operaciones en Brasil y
Latinoamérica. Trabajo 100% remoto desde Argentina.

## Experiencia

### Ivolution Sport Science — Data Scientist / Analytics Engineer
Remoto (Santa Fe, Argentina). Abr 2025 – Mar 2026 (ver "Para confirmar").
- Dashboards de monitoreo de fatiga neuromuscular en Metabase para 967 atletas en 13
  deportes, +10.000 mediciones. Sistema de referencia de la empresa, operativo tras mi salida.
- Sistema de alertas de estado atlético con 3 categorías (SUPERCOMPENSACIÓN / ATENCIÓN /
  FATIGADO) sobre métricas CMJ, IMTP y Drop Jump, con promedios móviles y umbrales dinámicos
  por percentiles.
- Modelos dbt para CMJ Rebound e IMTP (surrogate keys, tests, documentación) que unifican dos
  bases de datos de atletas.
- Pipelines ETL desde múltiples fuentes hacia BigQuery, con validación de calidad de datos y
  optimización de queries.
- Dashboards multilingüe (español / inglés / portugués) para equipos internacionales, vía
  parámetros JWT y CSV de traducción.
- Estándares de data quality y governance donde no existían procesos formales.
- También: custodia y defensa de bases de datos críticas (controles de acceso, auditoría,
  protección contra inconsistencias y accesos no autorizados).
- Stack en producción: BigQuery, dbt, Metabase, Python, SQL, n8n. También Power BI y Tableau.

## Proyectos reales verificables
Estos son los únicos que se pueden citar como prueba en un pitch.
- **Sistema de monitoreo Ivolution** (módulo DATA). Cifras arriba. Es trabajo interno de una
  empresa: se describe sin link.
- **E-Commerce Data Platform — Olist Brazil** (módulo DATA). Pipeline end-to-end sobre 100k+
  órdenes reales del mercado brasileño. PostgreSQL + dbt con 4 capas de modelos (staging,
  intermediate, marts), segmentación RFM, cohort retention y revenue trends en SQL, CI/CD con
  GitHub Actions. Dashboard en vivo: ecommerce-dashboard-puce.vercel.app
- **StackAdvisor** (módulo WEB). SaaS en React / Next.js / Node.js: plataforma de recomendación
  de tech stacks para developers y founders de Latinoamérica, con cuestionario gratuito y
  producto Blueprint de pago. En vivo: stackadvisor-nu.vercel.app
- **Jobly / radar-freelance** (módulo BOTS, en construcción real). Sistema de
  prospección que recolecta proyectos de varias fuentes, los puntúa contra mi perfil, redacta
  la propuesta con LLM en cascada gratuita y la entrega por Discord y un CRM web. Lo uso todos
  los días.
- Portfolio con demos y código: santiagomalak.is-a.dev

## Stack y nivel (autoevaluación del CV v3.0)
- Data: BigQuery avanzado (producción real), SQL avanzado (window functions, CTEs,
  optimización), dbt avanzado (modelos, tests, docs), Metabase avanzado, ETL avanzado,
  modelado dimensional avanzado, Python para análisis intermedio-avanzado, n8n intermedio.
- BI: Looker Studio avanzado, Power BI intermedio (DAX, Power Query), Tableau básico-intermedio.
- Full-Stack: React / Next.js avanzado, Node.js / REST APIs avanzado, TypeScript / JavaScript
  avanzado, Git / GitHub avanzado, Docker básico-intermedio.
- Machine Learning: scikit-learn intermedio, XGBoost intermedio (clasificación y series
  temporales), EDA y feature engineering intermedio-avanzado.
- Áreas secundarias (formación, no es mi posicionamiento principal): ciberseguridad
  (hardening Linux/Windows, redes, criptografía/PKI, incident response, forensics, OSINT).

## Idiomas
Español nativo. Portugués C1. Inglés: escrito profesional sólido, llamadas cortas sí
(ver "Para confirmar").

## Educación
- Tecnicatura en Tecnologías de la Programación, Universidad Provincial del Sudoeste (UPSO),
  modalidad remota. 2do año en curso, egreso 2026-27.
- Diplomatura en Data Science & Machine Learning, ICARO Asoc. Civil con la UNC (FCEFyN),
  250 hs. Finalizada en mayo 2025.
- Diplomatura en Ciberseguridad, USIL – Mundos E, 200 hs. Finalizada en septiembre 2025.

## Contacto profesional
santiagoaragonmalak@gmail.com · linkedin.com/in/aragonmalak · github.com/santiagomalak ·
santiagomalak.is-a.dev

## Para confirmar (el asistente NO debe asumir ninguna de estas)
1. Fechas en Ivolution: el CV v3.0 dice abr 2025 – mar 2026; el CV completo dice desde jun 2025.
2. Nivel de inglés: el CV v3.0 dice B2/C1 profesional; el CV completo y `01_perfil_core.md`
   dicen intermedio. Hasta que decidas se usa la versión conservadora.
3. La diplomatura de ciberseguridad: el CV completo la atribuye a la UNC 2024-2025; el CV v3.0
   a USIL – Mundos E (sep 2025).
4. Motivación: ¿qué te atrae de un proyecto o empresa? Sin esto, "¿por qué querés trabajar
   con nosotros?" sale con `[COMPLETAR]`.
5. Expectativa salarial para un rol fijo (`05_pricing_y_limites.md` cubre solo freelance).
6. Disponibilidad y horarios para un rol full-time o de más de 6 h por día.
7. Si Ivolution puede darse como referencia.
