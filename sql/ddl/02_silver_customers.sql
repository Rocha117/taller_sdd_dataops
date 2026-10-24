-- Stage 2 · Despliegue del modelo. Silver: registros válidos y deduplicados.
CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.silver_customers (
  customer_id     STRING    NOT NULL COMMENT 'Identificador único del cliente',
  name            STRING    NOT NULL COMMENT 'Nombre sin espacios al inicio ni al final',
  age             INT       NOT NULL COMMENT 'Edad en años',
  country_code    STRING    NOT NULL COMMENT 'Código de país en mayúsculas, existe en ref_paises',
  email           STRING    NOT NULL COMMENT 'Dato personal (PII). Email con formato válido',
  es_mayor_edad   BOOLEAN   NOT NULL COMMENT 'Derivada: age >= 18',
  es_contactable  BOOLEAN   NOT NULL COMMENT 'Derivada: registro válido y mayor de edad',
  _run_id         STRING    NOT NULL COMMENT 'Ejecución que generó la fila',
  _processed_at   TIMESTAMP NOT NULL COMMENT 'Momento del procesamiento'
)
USING DELTA
COMMENT 'Silver: solo registros válidos y deduplicados de la última ejecución. Contiene PII (email)';
