-- Stage 2 · Despliegue del modelo. Referencia de países (se carga desde data/reference/paises.csv).
CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.ref_paises (
  country_code  STRING NOT NULL COMMENT 'Código ISO de 2 letras',
  country_name  STRING NOT NULL COMMENT 'Nombre del país',
  region        STRING NOT NULL COMMENT 'Región del país'
)
USING DELTA
COMMENT 'Referencia de países: código, nombre y región. Se carga desde data/reference/paises.csv';
