---
id: plantillas_venta
version: 1
updated: 2026-09-21
carga: generacion de pitch
---

# PLANTILLAS DE VENTA

## Principio rector
El cliente lee 3 propuestas y elige. Las otras dos empiezan con "Hi, I'm a passionate developer
with 5 years of experience". **La tuya empieza hablando de su problema.**
Si en la primera línea aparece la palabra "yo", está mal escrita.

---

## PLANTILLA MAESTRA — Primer contacto (3 párrafos, 90–130 palabras)

**Párrafo 1 — DIAGNÓSTICO (1–2 frases).**
Reformulá su problema con una precisión técnica que demuestre que lo leíste y que ya lo resolviste antes.
Nombrá la dificultad real que él todavía no mencionó.

**Párrafo 2 — PLAN (2–3 frases + 3 bullets).**
Cómo lo resolvés, concreto: herramientas, pasos, entregable. Números: días, cantidad de workflows,
cantidad de campos. Nada de "podría ser" ni "dependiendo".

**Párrafo 3 — PRUEBA + CIERRE (2 frases).**
Una PoC o proyecto análogo con link. Cerrás con **una sola pregunta** que hace fácil responder.
Nunca "quedo a disposición". Nunca "espero tu respuesta".

---

### Versión ES
```
[PROBLEMA]: Por lo que describís, el cuello de botella no es conectar las dos apps
sino qué pasa cuando una responde tarde o duplicado — ahí es donde estas
automatizaciones suelen romperse en silencio.

[PLAN]: Te lo armo en n8n con esa parte resuelta desde el día uno:
• Workflow principal <A> → <B> con deduplicación por <campo>
• Error workflow con reintento y aviso a <Slack/email> si algo falla
• Video de 5 min + JSON exportado para que quede tuyo
Tiempo: <N> días hábiles. Rango: USD <X>–<Y> según <variable>.

[PRUEBA]: Hice algo muy parecido acá: <link PoC>.
¿El <sistema X> lo tenés self-hosted o en la nube? Con ese dato te cierro el número exacto hoy.
```

### Versión EN
```
[PROBLEM]: From your description, the bottleneck isn't connecting the two apps —
it's what happens when one of them responds late or duplicates a record. That's
where these automations usually break silently.

[PLAN]: I'd build it in n8n with that handled from day one:
• Main workflow <A> → <B> with deduplication on <field>
• Error workflow with retry + alert to <Slack/email> when something fails
• 5-min walkthrough video + exported JSON so you own it
Timeline: <N> business days. Range: USD <X>–<Y> depending on <variable>.

[PROOF]: I built something close to this here: <PoC link>.
Quick question: is your <system X> self-hosted or cloud? With that I can send you
the exact number today.
```

### Versión PT-BR (mercado menos competido — usala)
```
[PROBLEMA]: Pelo que você descreveu, o gargalo não é conectar os dois sistemas,
e sim o que acontece quando um deles responde com atraso ou duplica um registro.
É aí que essas automações costumam quebrar em silêncio.

[PLANO]: Eu montaria no n8n já com isso resolvido:
• Workflow principal <A> → <B> com deduplicação por <campo>
• Error workflow com retry e alerta no <Slack/e-mail>
• Vídeo de 5 min + JSON exportado, tudo seu
Prazo: <N> dias úteis. Faixa: USD <X>–<Y>.

[PROVA]: Fiz algo bem parecido aqui: <link>.
Seu <sistema X> é self-hosted ou cloud? Com essa info te mando o número fechado hoje.
```

---

## SEGUIMIENTO 1 — a las 48 h sin respuesta (2 frases, aporta valor)
```
Te dejo algo por si te sirve igual: <micro-insight concreto del problema,
ej. "el 80% de estas integraciones fallan por el rate limit de X, se resuelve con
un batch de 50 cada 60s">.
Si el proyecto sigue abierto, puedo arrancar <día concreto>.
```

## SEGUIMIENTO 2 — a los 6 días (1 frase, cierra el loop)
```
Cierro mi agenda de esta semana. ¿Lo dejo reservado o lo doy de baja?
```
**Máximo 2 seguimientos. Después, silencio.** Perseguir clientes baja tu precio.

---

## Prohibido en toda comunicación
- "Hola, ¿cómo estás?" como primera línea / "Hope this finds you well"
- Listar todo tu stack. El cliente de n8n no quiere saber que sabés dbt.
- "Soy estudiante" / "recién empiezo" / "sé que hay gente con más experiencia"
- Emojis en el primer contacto
- Adjuntar el CV si no lo pidieron
- Disculparse por el precio
