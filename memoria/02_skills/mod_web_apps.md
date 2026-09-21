---
id: mod_web_apps
modulo: WEB
version: 1
match_si_ticket_menciona: [react, next.js, node, express, typescript, javascript, api rest, frontend, backend, full stack, landing, crud, supabase, postgres, mongodb, dashboard web, saas mvp, stripe]
ticket_range_usd: [200, 450]
dias_entrega: [2, 5]
---

# MÓDULO WEB APPS

## Pitch de una línea
"Construyo la app interna o el MVP que necesitás en días, no meses: React + Node, desplegado, con auth y base de datos reales."

## Qué sé hacer
- **Frontend:** React, TypeScript, manejo de estado, formularios complejos, tablas con filtros, gráficos.
- **Backend:** Node.js + Express, diseño de API REST, validación, manejo de errores, rate limiting, jobs.
- **Datos:** PostgreSQL / Supabase, MongoDB. Modelado, migraciones, índices.
- **Auth:** JWT, sesiones, Supabase Auth, roles y permisos.
- **Deploy:** Vercel, Railway, Render, Docker. Variables de entorno y CI básico.
- **Integraciones:** pasarelas de pago, envío de emails transaccionales, webhooks entrantes.

## Entregables estándar
1. Repo con README de instalación que funciona en una máquina limpia.
2. Deploy funcionando en un entorno que el cliente controla.
3. Variables de entorno documentadas (`.env.example`).
4. Un recorrido en video del flujo principal.
5. 7 días de bugfix incluido (bugs, no features nuevas).

## Precios de referencia
| Trabajo | USD | Días |
|---|---|---|
| Landing + formulario conectado a CRM/DB | 150–220 | 1 |
| CRUD interno con auth (1 entidad principal) | 250–350 | 2–3 |
| MVP con 2–3 entidades, roles y dashboard | 380–450+ | 4–5 |
| Bugfix / feature sobre código ajeno | 120–200 | 0.5–1 |

## Preguntas de calificación
1. ¿Existe diseño o partimos de cero? (Sin diseño, uso una librería de componentes y lo digo en la propuesta.)
2. ¿Cuántos usuarios y qué roles?
3. ¿Quién mantiene esto después?
4. ¿Hay código existente? ¿Puedo verlo antes de cotizar? (Si no me dejan ver, cotizo +40%.)

## Señales de alarma
- "Un Uber/Airbnb pero simple" → descartar.
- Alcance con más de 6 pantallas por menos de $450 → descartar o proponer fase 1 recortada.
- Cliente que ya despidió a 2 devs del mismo proyecto → cobrar por hora, no fijo.
