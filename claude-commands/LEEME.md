# Cómo instalar estos slash commands

No pude escribir directo en `.claude/` desde acá (está protegida contra escritura remota,
por seguridad). Copialos vos con un comando:

**Windows (PowerShell, desde la raíz del proyecto):**
```powershell
New-Item -ItemType Directory -Force .claude\commands
Copy-Item claude-commands\*.md .claude\commands\ -Exclude LEEME.md
```

**Linux / Mac:**
```bash
mkdir -p .claude/commands && cp claude-commands/*.md .claude/commands/ && rm .claude/commands/LEEME.md
```

Después, dentro de `claude`, escribí `/` y van a aparecer:
`/postular`, `/copiloto`, `/retro`, `/diagnostico`.

Una vez copiados podés borrar esta carpeta `claude-commands/`.
