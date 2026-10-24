-- Stage 2 · Despliegue del modelo. Rechazados: filas con errores de calidad y su motivo.
CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.rechazados_customers (
  _run_id            STRING    NOT NULL COMMENT 'Ejecución que rechazó la fila',
  _row_number        INT       NOT NULL COMMENT 'Posición de la fila en el archivo de origen',
  customer_id        STRING             COMMENT 'Identificador del cliente; puede venir vacío',
  registro_original  STRING    NOT NULL COMMENT 'Dato personal (PII). Fila completa tal como llegó, en JSON',
  motivo             STRING    NOT NULL COMMENT 'Motivos de rechazo separados por "; " (ej. nombre_vacio; email_invalido)',
  _rejected_at       TIMESTAMP NOT NULL COMMENT 'Momento del rechazo'
)
USING DELTA
COMMENT 'Registros rechazados por reglas de calidad, con motivo, para corregir en el origen. Contiene PII';
