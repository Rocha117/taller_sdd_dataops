-- Stage 2 · Despliegue del modelo. Fase 2: agrega "monitoreo" a los valores de la columna stage.
-- Solo cambia el comentario (no borra nada) y se puede ejecutar las veces que sea.
ALTER TABLE {{catalog}}.{{schema}}.monitoreo_ejecuciones
  ALTER COLUMN stage COMMENT 'shift_left | despliegue_modelo | bronze | calidad | gold | monitoreo';
