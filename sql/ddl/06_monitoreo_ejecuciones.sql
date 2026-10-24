-- Stage 2 · Despliegue del modelo. Monitoreo: una fila por stage y por ejecución (se llena desde la Fase 2).
CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.monitoreo_ejecuciones (
  run_id            STRING    NOT NULL COMMENT 'Ejecución: <github.run_id>-<github.run_attempt>',
  stage             STRING    NOT NULL COMMENT 'shift_left | despliegue_modelo | bronze | calidad | gold',
  estado            STRING    NOT NULL COMMENT 'exito | advertencia | fallo',
  filas_entrada     BIGINT             COMMENT 'Filas que recibió el stage',
  filas_salida      BIGINT             COMMENT 'Filas que produjo el stage',
  filas_rechazadas  BIGINT             COMMENT 'Filas rechazadas por el stage',
  mensaje           STRING             COMMENT 'Detalle legible; nunca contiene emails',
  `trigger`         STRING    NOT NULL COMMENT 'pull_request | schedule | manual',
  git_sha           STRING    NOT NULL COMMENT 'Commit que se ejecutó',
  started_at        TIMESTAMP NOT NULL COMMENT 'Inicio del stage',
  finished_at       TIMESTAMP          COMMENT 'Fin del stage'
)
USING DELTA
COMMENT 'Monitoreo: una fila por stage y por ejecución';
