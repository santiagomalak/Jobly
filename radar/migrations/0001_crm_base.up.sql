-- 0001: modelo de CRM. Solo AGREGA tablas, columnas e índices: el código anterior sigue andando.
-- Las columnas nuevas de tickets no llevan REFERENCES (SQLite no deja borrarlas después con DROP COLUMN).

CREATE TABLE empresas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  nombre_norm TEXT NOT NULL UNIQUE,
  plataforma TEXT,
  verificado INTEGER,
  proyectos_previos INTEGER,
  calificacion REAL,
  gasto_total_usd INTEGER,
  notas TEXT DEFAULT ''
);

CREATE TABLE eventos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_fp TEXT NOT NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('cambio_etapa','envio','respuesta','entrevista','followup','nota','accion')),
  de_etapa TEXT,
  a_etapa TEXT,
  detalle TEXT DEFAULT '',
  fecha TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_eventos_ticket ON eventos(ticket_fp, fecha);

CREATE TABLE ingresos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ticket_fp TEXT,
  monto_usd INTEGER NOT NULL CHECK (monto_usd >= 0),
  estado TEXT NOT NULL CHECK (estado IN ('acordado','cobrado')),
  fecha TEXT NOT NULL,
  detalle TEXT DEFAULT ''
);
CREATE INDEX idx_ingresos_fecha ON ingresos(fecha);
CREATE INDEX idx_ingresos_ticket ON ingresos(ticket_fp);

CREATE TABLE importaciones (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fuente TEXT NOT NULL,
  politica TEXT NOT NULL DEFAULT 'ignorar',
  filas INTEGER DEFAULT 0,
  creadas INTEGER DEFAULT 0,
  actualizadas INTEGER DEFAULT 0,
  ignoradas INTEGER DEFAULT 0,
  con_error INTEGER DEFAULT 0,
  errores TEXT DEFAULT '[]',
  snapshot TEXT DEFAULT '[]',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  deshecha_at TEXT
);

CREATE TABLE mapeos_csv (
  fuente TEXT PRIMARY KEY,
  mapeo TEXT NOT NULL,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE login_intentos (
  ip TEXT PRIMARY KEY,
  fallos INTEGER NOT NULL DEFAULT 0,
  desde TEXT NOT NULL
);

ALTER TABLE tickets ADD COLUMN empresa_id INTEGER;
ALTER TABLE tickets ADD COLUMN tipo TEXT;
ALTER TABLE tickets ADD COLUMN etapa TEXT DEFAULT 'relevada';
ALTER TABLE tickets ADD COLUMN url_norm TEXT;
ALTER TABLE tickets ADD COLUMN clave_norm TEXT;
ALTER TABLE tickets ADD COLUMN presupuesto_min INTEGER;
ALTER TABLE tickets ADD COLUMN presupuesto_max INTEGER;
ALTER TABLE tickets ADD COLUMN moneda TEXT;
ALTER TABLE tickets ADD COLUMN periodo_pago TEXT;
ALTER TABLE tickets ADD COLUMN duracion_dias REAL;
ALTER TABLE tickets ADD COLUMN idioma TEXT;
ALTER TABLE tickets ADD COLUMN propuestas_recibidas INTEGER;
ALTER TABLE tickets ADD COLUMN score_oportunidad INTEGER;
ALTER TABLE tickets ADD COLUMN score_detalle TEXT;
ALTER TABLE tickets ADD COLUMN proxima_accion TEXT;
ALTER TABLE tickets ADD COLUMN proxima_accion_at TEXT;
ALTER TABLE tickets ADD COLUMN import_id INTEGER;

CREATE INDEX idx_tickets_url_norm ON tickets(url_norm);
CREATE INDEX idx_tickets_clave_norm ON tickets(clave_norm);
CREATE INDEX idx_tickets_etapa_accion ON tickets(etapa, proxima_accion_at);
CREATE INDEX idx_tickets_postulado ON tickets(postulado_at);
CREATE INDEX idx_tickets_import ON tickets(import_id);
CREATE INDEX idx_tickets_oportunidad ON tickets(score_oportunidad);

-- Etapa desde el estado legado. Un "perdido" cuyo primer cambio fue directo a perdido
-- (postulado_at = estado_at) fue un descarte, no una postulación rechazada.
UPDATE tickets SET etapa = CASE
  WHEN estado = 'postulado' THEN 'postulada'
  WHEN estado = 'respondido' THEN 'en_proceso'
  WHEN estado = 'ganado' THEN 'ganada'
  WHEN estado = 'perdido' AND postulado_at IS NOT NULL AND postulado_at = estado_at THEN 'descartada'
  WHEN estado = 'perdido' THEN 'rechazada'
  ELSE 'relevada' END;

UPDATE tickets SET tipo = CASE WHEN payload LIKE '%"tipo:%' THEN 'empleo' ELSE 'freelance' END
-- url_norm, clave_norm y score_oportunidad los completa Python (radar/migraciones.py: posterior_1)
