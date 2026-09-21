# FASE 2 — Estructura del servidor de Discord

## Por qué Discord y no Telegram/email
- Los webhooks son gratis, sin bot ni token para empezar.
- Los canales te dan **separación por etapa del embudo**: la alerta cruda no se mezcla con la propuesta lista.
- Podés pegar bloques de código largos (los pitches) y copiarlos de un toque.
- Funciona igual en el celular: revisás tickets desde cualquier lado.

## Crear el servidor (5 minutos)
1. Discord → `+` → **Crear mi propio servidor** → "Radar" (privado, solo vos).
2. Creá las categorías y canales de abajo.
3. En cada canal marcado con 🪝: **Editar canal → Integraciones → Webhooks → Nuevo webhook → Copiar URL**.
4. Pegá cada URL en tu `.env`.

## Estructura de canales

```
📡 RADAR
├── #01-radar-feed          🪝  Resumen de cada corrida + fuentes caídas
├── #02-propuestas-listas   🪝  ⭐ EL CANAL IMPORTANTE. Ticket + pitch listo para copiar
└── #09-errores             🪝  Fallos del script y de n8n

🎯 OPERACIÓN
├── #03-copiloto-chat           Pegás el mensaje del cliente → usás los prompts de /prompts
├── #04-postuladas              Copiás acá lo que enviaste. Es tu registro rápido del día
└── #05-en-conversacion         Clientes que respondieron. Uno por hilo

💰 CIERRE
├── #06-ganados                 Cada cierre con su monto. Sirve de tablero y de motivación
└── #07-entregados              Link al repo/entregable + "¿se convierte en PoC?"

🧠 SISTEMA
├── #08-memoria-sync            Cambios a la memoria .md, ideas de keywords nuevas
└── #10-retro-semanal           Domingo: pegás el log y corrés el prompt de postmortem
```

## Reglas de operación (esto es lo que hace que funcione)
- **#02 es el único canal que mirás durante el día.** El resto es archivo.
- Regla de los 15 minutos: si una alerta de #02 tiene score ≥ 65, se postula **dentro de los 15 min**.
  La velocidad de respuesta es la única ventaja real contra freelancers con más reseñas.
- Todo lo que postulás se copia a **#04-postuladas** con la hora. Sin excepción — ese canal
  es lo que después vuelca en `memoria/04_log_proyectos.md`.
- Cuando el cliente responde, abrís **hilo en #05** y ahí queda toda la conversación.
- Los domingos, 20 min en **#10** con el prompt de postmortem. Ajustás keywords y umbrales.

## Anatomía de la alerta que recibís en #02

```
┌─ EMBED ──────────────────────────────────────────┐
│ Need n8n expert to build CRM integration          │  ← título, clickeable al ticket
│ We use Bitrix24 and need a workflow that...       │  ← descripción recortada
│ Score: 72/100 │ Módulo: AUTOMATION │ USD 350      │
│ Fuente: upwork-n8n │ Motor: groq │ Match: n8n...  │
└───────────────────────────────────────────────────┘
PROPUESTA LISTA · Need n8n expert...
```
Por lo que describís, el cuello de botella no es conectar...
```
🔗 https://www.upwork.com/jobs/...
```

Copiás el bloque de código, lo revisás 30 segundos, lo pegás. Ese es todo el flujo.

## Rate limits a tener en cuenta
Un webhook de Discord aguanta ~5 mensajes cada 2 segundos. El radar manda 2 mensajes por
ticket, con un tope de `max_tickets_per_run` (12 por defecto) y reintento con espera
automática si recibe un 429. No lo subas arriba de 20.
