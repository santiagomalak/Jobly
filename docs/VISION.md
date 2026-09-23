---
id: vision
version: 1
updated: 2026-09-22
carga: referencia de producto, no la lee el motor
---

# VISIÓN — Jobly

Definido en sesión de entrevista estructurada el 2026-09-22. Esto es el "norte": lo que
decide qué construir primero y qué queda afuera. Si una feature nueva no sirve a esto,
se cuestiona antes de construirla.

## Outcome

Jobly deja de ser un aviso pasivo por Discord y pasa a ser el sistema operativo diario de
Santiago para buscar y conseguir laburo: el motor que ya existe (scoring + memoria + pitch)
+ un CRM con analytics + un bot de Discord que saca de encima toda la parte repetitiva de
postularse.

## Usuario y rutina

Santiago, todos los días a las 7am dedicándole la primera hora a postularse a la mayor
cantidad de matches posibles, después sigue con su vida y otros proyectos. Desde el celular
el resto del día vía Discord. En ~1 mes, el motor operativo de una PyME de soluciones
tecnológicas (web, IA, automatización, software a medida) que está por lanzar.

## Éxito — en orden de peso real, no solo plata

1. Postularse a la mayoría de los matches posibles con fricción casi cero — cero escribir
   respuestas repetidas a mano en cada postulación.
2. Meta de plata: piso USD 900/mes **sin techo**. Al principio, todo lo que entre se
   reinvierte en este proyecto hasta un techo aproximado de USD 6.000 (sin determinar del
   todo todavía).
3. Conseguir un laburo fijo O un proyecto de USD 60/día ya es éxito rotundo — el objetivo
   bajó de exigencia porque hoy el problema no es solo plata, es estar estancado.
4. Experiencia y networking cuentan como éxito tanto como la plata — un proyecto sin
   presupuesto pero que suma experiencia/portfolio puede valer la pena si se etiqueta como
   tal (no confundir con relajar los killers de scraping/ética — esto es sobre tickets
   reales de bajo presupuesto, no sobre bajar filtros éticos).
5. Analytics con onda "juego" — ver el avance de postulaciones/aceptaciones como progreso
   motivador, no una tabla fría.

## Mecanismo central: dos niveles de postulación

- **Fácil / de un click:** el bot arma todo (texto ya redactado o formulario pre-completado
  en un link). En Discord, un botón abre eso listo para que Santiago apriete el submit
  final **con su propio click humano en el navegador**. Nunca lo manda el bot solo, en
  ninguna plataforma, sin excepción.
- **Compleja (preguntas propias del formulario):** llega el ticket + pitch + link. Para
  las preguntas de screening ("qué frameworks conocés", "por qué querés trabajar con
  nosotros"), Santiago le pega la pregunta al bot (con límite de caracteres opcional) y
  recibe la mejor respuesta posible basada en su contexto completo. Copia y pega. Esto es
  el dolor más grande hoy: no es escribir el pitch, es responder lo mismo 100+ veces en
  postulaciones distintas.

## El "asistente personal" (contexto completo)

- Vive en un canal de Discord tipo `#info`: CV actualizado, carta de presentación, links
  a portfolio/LinkedIn.
- Alimentado por un archivo `.md` estructurado (no un PDF crudo — más fácil de parsear e
  inyectar en el prompt). Reemplaza/complementa `santiago-data/` (que hoy son PDFs sin uso
  por el código).
- Otro canal para ir actualizando esa info con el tiempo.
- Puede generar textos "sobre mí" u otro contenido personalizado a pedido, basado en todo
  lo que sabe.

## Restricciones duras (no negociables)

- **Nunca** se postula/envía nada sin que Santiago apriete el botón final él mismo, en
  ninguna plataforma.
- **No scraping de X/Instagram/LinkedIn.** ToS + riesgo real de baneo de cuenta + (para
  Instagram específicamente) choca con la regla ética propia de no scrapear datos
  personales. Nada de cuentas fake/VPN/VMs para evadir esto tampoco — mismo problema, peor,
  porque además es evasión deliberada.
- No relajar los killers de scraping de datos personales ni los filtros éticos de
  `memoria/02_skills/mod_scraping.md`.
- Fase 1 sin costo de servidor fijo. El VPS (~USD 6-7/mes) recién en Fase 2, cuando el
  resto ya funcione y esté probado.

## Fuera de alcance (por ahora)

- IA de voz en canal de Discord para generar contenido de LinkedIn — idea a futuro, fase 3+.
- Orquestación completa multi-cliente de la PyME — cuando lance en ~1 mes.
- Auto-postulación real desatendida en cualquier plataforma.
- LinkedIn/X/Instagram como fuente de datos (ver restricciones).

## Fuentes de tickets — estado real (auditado, no de memoria)

| Fuente | Estado |
|---|---|
| RemoteOK | funciona (API pública) |
| WeWorkRemotely | funciona (RSS) |
| Reddit | roto (403) — pendiente pasar a API oficial OAuth |
| HN "seeking freelancer" | funciona (arreglado 2026-09-22) |
| Remotive | funciona (API pública, uso personal permitido) |
| **Google Sheets/Excel** | **funciona** — fuente `sheet` (CSV publicado) y, en el CRM web, "Agregar": una oferta suelta o filas pegadas desde la planilla. Se puntúan igual que todo lo demás |
| Upwork | muerto (RSS descontinuado 20/08/2024) — solo queda su API oficial (OAuth, requiere approval) |
| EducaciónIT Empleos | sin API/RSS. Útil para el objetivo de "laburo fijo", no para tickets de 1-3 días |
| Get On Board, Dice, Indeed, Glassdoor | sin camino automatizable legítimo, o mal fit de negocio |
| Workana, Freelancer.com, Torre.ai | candidatos sin investigar todavía |

## Roadmap de infraestructura (fases)

1. **Fase 1 (hecha en código el 23/09, falta desplegar — `docs/DEPLOY.md`):** todo gratis.
   GitHub Actions cron para el motor, **CRM web en Vercel** (pipeline, detalle, asistente
   `Preguntar`, `Agregar`/importar planilla) y base compartida en Turso (`radar/db.py`, por HTTP).
   Pendiente de esta fase: bot de Discord con comandos de barra (`/pregunta`, `/ticket`) — Discord
   los entrega por HTTP, así que encaja en el mismo Vercel sin servidor dedicado.
2. **Fase 2:** VPS (~USD 6-7/mes) para tener el bot escuchando 24/7 sin depender de
   comandos de barra únicamente, una vez que el resto ya esté probado y funcionando.
3. **Fase 3+ (futuro, no ahora):** IA de voz en Discord para ideación de contenido de
   LinkedIn. Orquestación completa cuando la PyME esté lanzada.
