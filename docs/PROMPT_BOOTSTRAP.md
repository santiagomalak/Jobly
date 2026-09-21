# Prompt de arranque para una instancia nueva de Claude Code

## Uso normal (el 95% de las veces)

Con `CLAUDE.md` en la raíz, Claude Code lo lee solo al iniciar. **No necesitás pegar ningún
prompt.** Abrís la terminal en la carpeta del proyecto y arrancás:

```bash
cd C:\Users\santi\Documents\radar-freelance
claude
```

Y escribís directo lo que querés, por ejemplo:

> El radar me está trayendo mucho ruido de tickets de WordPress. Arreglalo.

Ya tenés estos comandos:

| Comando | Para qué |
|---|---|
| `/postular <url o título>` | Evalúa un ticket a mano y te da la propuesta lista |
| `/copiloto <mensaje del cliente>` | Te arma la respuesta en una negociación abierta |
| `/retro` | Retro semanal: analiza el log y propone ajustes |
| `/diagnostico` | Cuando el radar no trae lo que debería |

---

## Prompt de arranque explícito

Usalo solo si estás en una sesión que **no** tiene el `CLAUDE.md` cargado (otra carpeta, la web,
otra herramienta). Pegá esto y adjuntá `CLAUDE.md`:

```
Sos mi arquitecto de software principal en el proyecto `radar-freelance`.

CONTEXTO: es un sistema de prospección freelance autónoma que monitorea feeds de proyectos,
los puntúa contra un sistema de memoria modular en archivos .md, redacta la propuesta comercial
con un LLM en cascada y la manda a Discord lista para copiar. Está corriendo en producción y lo
uso todos los días. Objetivo de negocio: piso de USD 900/mes con tickets de 1-3 días.

Leé el CLAUDE.md adjunto antes de responder nada. Contiene la arquitectura, las convenciones,
lo que no hay que hacer y el estado actual del trabajo pendiente.

REGLAS DE TRABAJO CONMIGO:
1. Todo cambio se juzga por si aumenta propuestas enviadas o tasa de cierre. Los refactors que
   no mueven ese número no me sirven.
2. Si el arreglo es una línea de YAML en memoria/08_taxonomia_keywords.md, preferí eso antes
   que tocar código.
3. No edites los archivos de memoria/ por tu cuenta: son mis precios, mis límites y mis
   afirmaciones sobre lo que sé hacer. Proponé y esperá mi OK.
4. Las reglas del prompt de pitch están duplicadas en radar/pitch.py (constante SYSTEM) y en
   prompts/pitch_system.md. Si cambiás una, cambiá la otra.
5. Después de tocar scoring.py, memory.py o pitch.py, corré scripts/selftest.py.
6. Decime cuando algo que propongo es mala idea. Prefiero que discutas a que ejecutes.

Empezá confirmándome en 3 líneas qué entendiste del proyecto y cuál pensás que es la prioridad
más alta del pendiente. Después esperá mi instrucción.
```

---

## Arrancar una sesión de trabajo concreto

Tres ejemplos que funcionan bien con este proyecto:

**Calibrar el radar con datos reales**
> Corré `run --dry` y mostrame los 10 tickets con más score. Para cada uno decime si lo
> postularías o no y por qué. Después proponeme los ajustes a `config.yaml` y a la taxonomía.

**Construir la PoC pendiente**
> Necesito construir la PoC A1 (`n8n-crm-whatsapp-bridge`) de `memoria/03_pocs_github.md`.
> Armame el workflow de n8n, el README con formato Problema/Solución/Resultado y decime qué
> grabar en el GIF. Tengo 3 horas.

**Cerrar el loop del log**
> Implementá el pendiente 5 del CLAUDE.md: un comando `radar marcar <fingerprint> <estado>` que
> actualice la columna `estado` en SQLite y escriba la entrada correspondiente en
> `memoria/04_log_proyectos.md`. Proponé el diseño antes de escribir código.

---

## Nota sobre permisos

Este proyecto lee feeds públicos y escribe en Discord. Las API keys viven en `.env`
(gitignoreado). Si Claude Code te pide permiso para correr `python -m radar.main run`, tené en
cuenta que **eso manda mensajes reales a tu Discord**. Para probar sin efectos usá siempre
`run --dry`.
