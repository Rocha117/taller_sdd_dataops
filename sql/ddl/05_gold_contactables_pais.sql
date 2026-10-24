-- Stage 2 · Despliegue del modelo. Gold: indicador de contactables por país, sin datos personales.
CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.gold_contactables_pais (
  country_code           STRING        NOT NULL COMMENT 'Código de país; ZZ = sin país o país desconocido',
  country_name           STRING        NOT NULL COMMENT 'Nombre del país; "Sin país" para ZZ',
  region                 STRING        NOT NULL COMMENT 'Región; "Sin región" para ZZ',
  clientes_unicos        BIGINT        NOT NULL COMMENT 'Clientes únicos del archivo de origen en ese país',
  clientes_contactables  BIGINT        NOT NULL COMMENT 'Clientes válidos y mayores de edad',
  pct_contactables       DECIMAL(5,2)  NOT NULL COMMENT 'clientes_contactables / clientes_unicos * 100',
  _run_id                STRING        NOT NULL COMMENT 'Ejecución que calculó la fila',
  _updated_at            TIMESTAMP     NOT NULL COMMENT 'Momento del cálculo'
)
USING DELTA
COMMENT 'Gold: indicador de clientes contactables por país. Sin datos personales';
