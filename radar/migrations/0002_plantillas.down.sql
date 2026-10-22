DROP INDEX IF EXISTS idx_tickets_plantilla;
ALTER TABLE tickets DROP COLUMN plantilla_id;
DROP TABLE IF EXISTS plantillas;
