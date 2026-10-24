-- Stage 2 · Despliegue del modelo. Bronze: dato crudo de customers.csv.
CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.bronze_customers (
  customer_id   STRING    COMMENT 'Identificador del cliente, tal como llega del CRM',
  name          STRING    COMMENT 'Nombre, tal como llega',
  age           STRING    COMMENT 'Edad como texto: puede venir vacía o no numérica',
  country       STRING    COMMENT 'Código de país, tal como llega',
  email         STRING    COMMENT 'Dato personal (PII). Email, tal como llega',
  _run_id       STRING    NOT NULL COMMENT 'Ejecución que cargó la fila',
  _source_file  STRING    NOT NULL COMMENT 'Ruta del archivo de origen',
  _row_number   INT       NOT NULL COMMENT 'Posición de la fila en el archivo (1 = primera fila de datos)',
  _ingested_at  TIMESTAMP NOT NULL COMMENT 'Momento de la carga'
)
USING DELTA
COMMENT 'Bronze: dato crudo de customers.csv, con historia por ejecución';
