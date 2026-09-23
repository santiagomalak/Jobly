# Desplegar Jobly (Turso + Vercel + GitHub Actions)

Tres piezas, una base compartida:

```
GitHub Actions (cron 09:00 y 18:00 ART)  ──escribe──►  Turso (base)  ◄──lee/escribe──  Vercel (CRM web)
        radar run → Discord                                                     login con JOBLY_PASSWORD
```

Por qué así: Vercel no guarda archivos entre ejecuciones, así que SQLite local no sirve ahí.
Turso habla SQLite; el código ya está listo (`radar/db.py`). Todo entra en planes gratis.
Nota: el plan Hobby de Vercel es de uso personal, no comercial. Si Jobly pasa a operar
la PyME, revisá sus términos y pasá a un plan pago.

## 1. Turso (10 min)

1. Creá cuenta en turso.tech y una base llamada `jobly` (elegí la región más cercana).
2. En la página de la base copiá la **URL** (`libsql://jobly-<tu-org>.turso.io`).
3. Generá un **token** de la base con permisos de lectura y escritura, sin expiración.
   (Por CLI: `turso db tokens create jobly`).
4. Guardá los dos valores: son `TURSO_DATABASE_URL` y `TURSO_AUTH_TOKEN`.

No hace falta crear tablas: `Store` las crea en la primera conexión.

## 2. Secrets de GitHub (5 min)

Repo → Settings → Secrets and variables → Actions → New repository secret. Cargá:

| Secret | De dónde sale |
|---|---|
| `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` | Paso 1 |
| `GROQ_API_KEY`, `OPENROUTER_API_KEY` | tu `.env` local |
| `DISCORD_WEBHOOK_RADAR`, `DISCORD_WEBHOOK_PROPUESTAS`, `DISCORD_WEBHOOK_ERRORES` | tu `.env` local |
| `JOBLY_URL` | la URL de Vercel del paso 3 (sin barra final). Hace que cada alerta de Discord traiga un link directo al ticket. Cargala después de desplegar |
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` | opcionales, ver "Reddit" abajo |

Después: pestaña **Actions** → workflow `radar` → **Run workflow**. Tiene que terminar en verde y
mandar el resumen al canal `#radar`. (La primera corrida evalúa todo como nuevo: es normal.)

## 3. Vercel (10 min)

1. vercel.com → Add New → Project → importá `santiagomalak/Jobly` (autorizá el acceso al repo privado).
2. Vercel detecta Flask solo (`app.py` + `requirements.txt`). No cambies el build.
3. Antes de Deploy, cargá estas **Environment Variables**:

   | Variable | Valor |
   |---|---|
   | `JOBLY_PASSWORD` | una contraseña LARGA (es lo único que protege tus datos) |
   | `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` | Paso 1 |
   | `GROQ_API_KEY`, `OPENROUTER_API_KEY` | tu `.env` local |
   | `LLM_TIMEOUT` | `15` |
   | `LLM_MAX_WAIT` | `8` (tope de espera ante límites de los proveedores gratis) |

4. Deploy. Abrí la URL, entrá con la contraseña y probá: Pipeline, Agregar, Preguntar.
5. Si la página dice "Falta configurar...", falta una variable: la app falla cerrada a propósito.

## 4. Verificación rápida

- `https://<tu-app>.vercel.app/healthz` responde `{"ok": true}` sin login.
- Cualquier otra ruta sin sesión te manda a `/login`.
- En Agregar, cargá una oferta de prueba: aparece en Pipeline en el celular y en la PC.

## Reddit (opcional, 5 min)

r/forhire, r/slavelabour y r/jobbit son de las pocas fuentes con micro-proyectos reales, pero
Reddit bloquea el acceso anónimo (403). Con su API oficial de solo lectura funcionan:

1. reddit.com/prefs/apps → "create another app" → tipo **script**, redirect uri `http://localhost:8080`.
2. Copiá el **client id** (debajo del nombre de la app) y el **secret**.
3. Cargalos como `REDDIT_CLIENT_ID` y `REDDIT_CLIENT_SECRET` en tu `.env` y en los secrets de GitHub.
   `REDDIT_USER_AGENT` = `python:jobly-radar:1.0 (by /u/tu_usuario)`.

Sin estas variables la fuente sigue fallando en silencio y el resto del radar funciona igual.

## Local

```
python -m radar.main serve      # http://127.0.0.1:8000 (necesita JOBLY_PASSWORD en .env)
```
Sin `TURSO_*` usa `data/radar.sqlite`. Con `TURSO_*` en tu `.env`, tu PC apunta a la base
compartida: cuidado con `run` (sin `--dry`), que escribe ahí y manda a Discord.

## Higiene de claves

Las claves de Groq, OpenRouter y los webhooks de Discord pasaron por el chat de la sesión de
desarrollo. Cuando termines el deploy, rotalas (nuevas claves en cada proveedor, actualizadas en
`.env`, GitHub y Vercel) si querés dormir tranquilo.
