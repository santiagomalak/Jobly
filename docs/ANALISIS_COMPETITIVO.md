---
id: analisis_competitivo
version: 1
updated: 2026-09-23
---

# Análisis competitivo — Jobly

Investigado el 23/09/2026. **Advertencia sobre las fuentes:** casi todo lo público sobre
estas herramientas son blogs comparativos escritos por las propias herramientas o por sitios de
afiliados. Los precios y porcentajes de abajo son *reportados*, no auditados. Donde una página
oficial no se pudo leer (Upwork devolvió 403) se dice explícitamente.

## 1. Resumen

- Jobly no compite con nadie en una sola cosa: junta lo que hoy exige 3-4 herramientas
  (rastreador, redactor de propuestas, asistente de formularios, alertas) y lo hace **gratis, en
  español y sin automatizar plataformas de terceros**.
- Su ventaja real no es tecnológica sino de **postura**: el mercado se está partiendo entre
  "postular en masa con bots" (cuentas restringidas, 1-6% de respuesta) y "copilotos con humano
  al mando". Jobly es del segundo grupo, que es el que las plataformas toleran.
- Su debilidad real es de **oferta**: las fuentes públicas casi no traen micro-proyectos. Las
  herramientas de alertas de Upwork resuelven eso con acceso que Jobly no debe replicar.
- Lo que más falta para tu KPI (5 propuestas/semana, 1 cierre): captar ofertas de Workana y
  LinkedIn sin scraping. Ya está resuelto con el marcador "Guardar en Jobly" (ver §5).

## 2. Mapa competitivo

| Categoría | Ejemplos | Qué hacen | Precio reportado | Límite o riesgo |
|---|---|---|---|---|
| Rastreadores de búsqueda (CRM) | Huntr, Teal, Careerflow | Kanban de postulaciones, clipper de ofertas, notas, contactos, recordatorios, CV por oferta | Huntr gratis hasta ~40-100 trabajos y USD 10/mes ilimitado; Teal gratis y Teal+ USD 29/30 días; Careerflow ~USD 14/mes anual | Pensados para empleo en relación de dependencia y en inglés; no traen oferta propia |
| Copilotos de formularios | Simplify | Extensión que autocompleta formularios en 100+ portales (Workday, Greenhouse, Lever…) | Gratis | Solo ATS de empleo; el humano envía |
| Auto-apply (bots) | LazyApply, Sonara, JobCopilot, AIApply, Jobright | Envían solicitudes solos, en volumen | LazyApply USD 99-249/año | Callback 1-6% en los totalmente automáticos; ~23% de usuarios de automatización restringidos por LinkedIn en 90 días (reportado); LazyApply ~2,1-2,4/5 en Trustpilot |
| Alertas y propuestas para Upwork | GigRadar, Vollna, UpAlerts, UpCat | Alertas casi en tiempo real, IA para redactar, algunas con auto-bidding | Vollna desde ~USD 16/mes (otros reportes van a USD 200-470); Auto 50 propuestas ≈ USD 59 | El auto-bidding viola la política de Upwork; las bajas por automatización habrían subido ~23% en 2025 (reportado) |
| Marketplaces LATAM | Workana | 2M+ de freelancers, ES/PT, base en Argentina | Comisión al freelancer 20% (primeros USD 300 de un cliente nuevo), 10% (300-3.000), 5% (más); 4,5% al cliente | Sin API pública; tarifas más bajas que Upwork (USD 15-40/h) pero menos competencia |
| Bolsas de empleo remoto | Himalayas, Remotive, RemoteOK, Jobicy | Listados con API pública | Gratis (piden atribución) | Mayoría Senior y full-time; ya integradas en Jobly |

## 3. Dónde Jobly gana

1. **Cumple las reglas del juego.** Según los resúmenes consultados, Upwork permite IA para
   redactar y para avisar de ofertas siempre que una persona revise y envíe, y prohíbe cualquier
   herramienta que envíe propuestas sin un clic humano; LinkedIn prohíbe bots en su Acuerdo de
   Usuario (§8.2). Jobly nunca envía nada: el botón final es tuyo. Verificar la política vigente
   de Upwork en su Help Center ("Use bots and other automation properly"): no se pudo leer directo.
2. **Costo cero.** Cuentas gratis de Turso, Vercel Hobby, GitHub Actions, Groq y OpenRouter. Un
   rastreador comparable cuesta USD 10-29/mes; un auto-apply, USD 99-249/año.
3. **Honestidad verificable.** El asistente solo afirma lo que está en tu contexto, copia los
   niveles del CV y marca `[COMPLETAR]`. Los bots de masa no personalizan por oferta (Sonara y
   LazyApply explícitamente no), que es justo lo que más importa según los análisis de mercado.
4. **Un solo flujo para dos objetivos.** Proyecto (plan y precio) y puesto (carta) en el mismo
   pipeline, más seguimiento a las 48 h y 6 días. Ninguno de los rastreadores nombrados distingue
   freelance de empleo.
5. **Español, portugués y Argentina.** Las herramientas de la lista son anglosajonas; Himalayas
   con `country=AR` y el idioma de las respuestas son diferenciales concretos para vos.
6. **Tus datos son tuyos.** Base propia, sin suscripción que se corte.

## 4. Dónde Jobly pierde

| Brecha | Quién la cubre | Cómo se cierra sin violar reglas |
|---|---|---|
| Oferta de micro-proyectos en tiempo real (Upwork, Freelancer) | GigRadar, Vollna | No replicar: usan accesos que Jobly no debe usar. Compensar con el marcador y Workana manual |
| Autocompletar formularios | Simplify | Extensión propia: mucho trabajo, poco retorno para tu volumen. Mejor el asistente `Preguntar`, que ya resuelve el 80% de la escritura |
| CV a medida por oferta con puntaje ATS | Teal, Huntr, Jobscan | El panel "Encaje con tu perfil" cubre lo honesto (qué tenés y qué no); reescribir el CV por oferta es la próxima brecha |
| Cobertura de LinkedIn, Indeed, Workana | Todos | Solo por carga manual o con permiso de cada plataforma |
| Preparación de entrevistas | Careerflow y similares | Candidato natural para una versión con LLM sobre tu contexto |
| Multiusuario | Todos | No es objetivo hoy; sí lo sería al lanzar la PyME |
| App nativa | Huntr, Teal | La versión instalable (PWA) alcanza |

## 5. Lo que se hizo a partir de este análisis

- **Guardar en Jobly (marcador).** Equivale al clipper de Teal, pero seleccionás vos el texto y
  nada se automatiza en el sitio de origen: sirve para Workana, LinkedIn o cualquier portal.
- **Encaje con tu perfil.** Equivale al "keyword gap" de Teal: lo que el aviso pide y ya tenés,
  lo que menciona y no figura en tu memoria, y los años exigidos.
- **Analítica.** Qué módulo y fuente convierten y tu ritmo semanal (las tasas aparecen desde 5
  envíos por grupo).
- **App instalable en el celular** (manifest + ícono).
- Recolección en paralelo (de ~4,5 a ~1 minuto).

## 6. Próximo, por impacto en el KPI

1. **Postular más desde donde hay proyectos:** Workana con el marcador, todos los días a las 7.
2. **Cerrar el ciclo con datos:** después de ~30 postulaciones, mirar la analítica y ajustar la
   taxonomía (dice qué módulo y qué fuente responden).
3. **Adaptar el CV por oferta** con la regla de honestidad ya usada (solo hechos de memoria).
4. **Preparación de entrevista** por oferta.
5. **Permiso o API oficial** de Upwork y Freelancer si algún día justifican el esfuerzo; hoy no.

## 7. Posicionamiento

"El copiloto honesto y gratuito para freelancers y perfiles junior de Latinoamérica: encuentra,
puntúa, redacta con tus hechos reales y te acompaña hasta el seguimiento, pero el envío lo
hacés vos." Contra el spray automático (que quema cuentas) y contra el rastreador que solo
ordena lo que ya encontraste.

## Fuentes consultadas (23/09/2026)

Comparativas de rastreadores: prentus.com, jobshinobi.com, resumly.ai, jobscoutly.com.
Auto-apply: jobscan.co/blog/auto-apply-job-tools (leído completo), resumly.ai, remotejobassistant.com,
careery.pro. Upwork: gigradar.io, giguphq.com, uphunt.io, vollna.com/pricing (resultados de
búsqueda; la página de Upwork Help no se pudo leer). Workana: tecla.io, waco3.io, vivirdefreelance.com.
Términos de APIs: himalayas.app/docs/remote-jobs-api, freelancer.com/about/terms (§33).
