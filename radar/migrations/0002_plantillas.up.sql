-- Biblioteca de propuestas: plantillas reutilizables y qué plantilla se usó en cada envío.
CREATE TABLE IF NOT EXISTS plantillas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'freelance' CHECK (tipo IN ('freelance', 'empleo', 'seguimiento')),
    idioma TEXT NOT NULL DEFAULT 'es',
    cuerpo TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
ALTER TABLE tickets ADD COLUMN plantilla_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_tickets_plantilla ON tickets(plantilla_id);
