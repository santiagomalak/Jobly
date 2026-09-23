"""Lector del sistema de memoria .md modular.

El motor NO carga todo el CV: carga el perfil core + el módulo que hizo match.
Eso es lo que hace que un ticket de solo-n8n obtenga un pitch 100% de n8n.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


class Memory:
    def __init__(self, memory_dir: Path):
        self.dir = Path(memory_dir)
        if not self.dir.exists():
            raise FileNotFoundError(f"No existe el directorio de memoria: {self.dir}")

    # ---------- utilidades ----------
    @staticmethod
    def _strip_frontmatter(text: str) -> tuple[dict[str, Any], str]:
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                try:
                    meta = yaml.safe_load(parts[1]) or {}
                except yaml.YAMLError:
                    meta = {}
                return meta, parts[2].strip()
        return {}, text.strip()

    def read(self, relative: str) -> str:
        path = self.dir / relative
        if not path.exists():
            return ""
        _, body = self._strip_frontmatter(path.read_text(encoding="utf-8"))
        return body

    # ---------- piezas ----------
    def perfil_core(self) -> str:
        return self.read("01_perfil_core.md")

    def modulo(self, nombre: str) -> str:
        """nombre: AUTOMATION | DATA | WEB | SCRAPING | BOTS"""
        mapping = {
            "AUTOMATION": "02_skills/mod_automation_n8n.md",
            "DATA": "02_skills/mod_data_pipelines.md",
            "WEB": "02_skills/mod_web_apps.md",
            "SCRAPING": "02_skills/mod_scraping.md",
            "BOTS": "02_skills/mod_bots_discord.md",
        }
        return self.read(mapping.get(nombre.upper(), ""))

    def pocs_de(self, modulo: str) -> str:
        """Sección del módulo en 03_pocs_github.md, SIN las PoCs ⬜ PENDIENTE.

        Una PoC pendiente no existe: si llega al prompt, el LLM la cita como trabajo hecho.
        Devuelve "" si no queda ninguna fila real.
        """
        full = self.read("03_pocs_github.md")
        pattern = rf"## MÓDULO {re.escape(modulo.upper())}(.*?)(?=\n## |\Z)"
        m = re.search(pattern, full, re.S)
        if not m:
            return ""
        lineas = [ln for ln in m.group(1).strip().splitlines() if "⬜" not in ln]
        filas = [ln for ln in lineas if ln.startswith("|")]
        if len(filas) <= 2:  # solo encabezado y separador
            return ""
        return "\n".join(lineas).strip()

    def contexto_personal(self) -> str:
        return self.read("09_contexto_personal.md")

    def proyectos_reales(self, modulo: str) -> str:
        """Proyectos verificables de 09_contexto_personal.md que declaran este módulo."""
        full = self.contexto_personal()
        sec = re.search(r"## Proyectos reales verificables(.*?)(?=\n## |\Z)", full, re.S)
        if not sec:
            return ""
        elegidos = []
        for bloque in re.split(r"\n(?=- \*\*)", sec.group(1)):
            tag = re.search(r"\(módulos? ([^)]*)\)", bloque)
            if tag and modulo.upper() in tag.group(1).upper():
                elegidos.append(bloque.strip())
        return "\n".join(elegidos)

    def plantillas(self) -> str:
        return self.read("06_plantillas_venta.md")

    def objeciones(self) -> str:
        return self.read("07_objeciones.md")

    def pricing(self) -> str:
        return self.read("05_pricing_y_limites.md")

    def taxonomia(self) -> dict[str, Any]:
        """Extrae el bloque ```yaml de 08_taxonomia_keywords.md."""
        raw = self.read("08_taxonomia_keywords.md")
        m = re.search(r"```yaml(.*?)```", raw, re.S)
        if not m:
            return {"modulos": {}, "killers": [], "bonus": {}, "penalizaciones": {}}
        data = yaml.safe_load(m.group(1)) or {}
        data.setdefault("modulos", {})
        data.setdefault("killers", [])
        data.setdefault("bonus", {})
        data.setdefault("penalizaciones", {})
        return data

    # ---------- contexto para el LLM ----------
    def contexto_pitch(self, modulo: str) -> str:
        """El paquete mínimo y suficiente que recibe el LLM. Nunca el CV completo."""
        bloques = [
            "=== PERFIL CORE ===",
            self.perfil_core(),
            f"\n=== MÓDULO ACTIVADO: {modulo} ===",
            self.modulo(modulo),
            f"\n=== PRUEBAS DISPONIBLES ({modulo}) ===",
            self.pocs_de(modulo) or "(sin PoCs publicadas aún para este módulo)",
            f"\n=== PROYECTOS REALES ({modulo}) — única prueba que podés citar ===",
            self.proyectos_reales(modulo) or "(ninguno para este módulo: no cites proyectos)",
            "\n=== REGLAS DE REDACCIÓN ===",
            self._reglas_redaccion(),
        ]
        return "\n".join(b for b in bloques if b)

    def _reglas_redaccion(self) -> str:
        plant = self.plantillas()
        m = re.search(r"## Principio rector(.*?)(?=\n---)", plant, re.S)
        principio = m.group(1).strip() if m else ""
        m2 = re.search(r"## Prohibido en toda comunicación(.*)", plant, re.S)
        prohibido = m2.group(1).strip() if m2 else ""
        return f"{principio}\n\nPROHIBIDO:\n{prohibido}"
