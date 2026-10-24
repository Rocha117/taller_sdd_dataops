# Fase 2 · Pipeline de punta a punta · Plan

> Tareas en el orden en que se construyen. Cada tarea indica el archivo que crea o modifica. Respeta [requerimientos.md](requerimientos.md) y el [stack tecnológico](../../constitucion/stack-tecnologico.md). Se trabaja solo en la rama `feat/fase-2-pipeline-e2e`.

## Grupo 1 · Base común

- [ ] **1.1** Crear `scripts/metricas.py`:
  - un contexto que mide `started_at` y `finished_at` (UTC), guarda `estado`, filas y `mensaje`;
  - al salir, también con excepción, escribe la salida `metricas` (JSON) en `GITHUB_OUTPUT`;
  - una función para publicar otras salidas (el `run_id`).
- [ ] **1.2** Agregar `UMBRAL_RECHAZO_PCT = 50` a `scripts/reglas_calidad.py`, con una función `supera_umbral(rechazadas, total)`.
- [ ] **1.3** Crear `tests/test_metricas.py`: el JSON tiene todas las claves, se escribe aunque haya una excepción, y sin `GITHUB_OUTPUT` no falla.

## Grupo 2 · Stage 1 · Shift-left ampliado

- [ ] **2.1** Modificar `scripts/validar_csv.py`:
  - bloquea (código `1` y `::error::`) con `% filas con error >= UMBRAL_RECHAZO_PCT`;
  - el texto del reporte indica el umbral;
  - publica métricas con `metricas.py`.
- [ ] **2.2** Crear `tests/fixtures/mayoria_con_error.csv`, con 50 % o más de filas con error y la estructura correcta.
- [ ] **2.3** Actualizar `tests/test_validar_csv.py`:
  - `mayoria_con_error.csv` bloquea;
  - el CSV real sigue en verde con advertencia;
  - el límite exacto de 50 % bloquea;
  - las métricas publicadas son las esperadas.

## Grupo 3 · Stage 2 · Ajustes al despliegue

- [ ] **3.1** Crear `sql/ddl/07_comentario_stage_monitoreo.sql` (`ALTER TABLE ... ALTER COLUMN stage COMMENT ...`).
- [ ] **3.2** Modificar `scripts/desplegar_modelo.py`:
  - `MERGE` condicional (`WHEN MATCHED AND (...)`);
  - acepta scripts `ALTER` además de `CREATE`;
  - publica métricas.
- [ ] **3.3** Actualizar `tests/test_contrato.py`:
  - distingue los DDL `CREATE TABLE` (01 a 06, comparados con el contrato) de los `ALTER` (07 en adelante);
  - ningún script tiene `DROP`;
  - el `MERGE` es condicional.

## Grupo 4 · Stage 3 · Ingesta a Bronze

- [ ] **4.1** Crear `scripts/ingestar_bronze.py`:
  - lee el CSV con `validar_csv.leer_filas`;
  - borra el `_run_id` de esta ejecución;
  - hace un `INSERT` parametrizado por lotes de los campos crudos, con `_run_id`, `_source_file`, `_row_number` y `_ingested_at`;
  - cuenta las filas cargadas y falla si no coinciden;
  - publica `run_id` y métricas.
- [ ] **4.2** Crear `tests/test_ingesta_bronze.py`, con un cursor falso y sin Databricks:
  - los parámetros conservan los espacios del CSV;
  - `_row_number` empieza en 1;
  - el `DELETE` va antes del `INSERT`;
  - un conteo distinto hace fallar el stage;
  - el log no contiene `@`.

## Grupo 5 · Stage 4 · Calidad de datos

- [ ] **5.1** Crear `scripts/calidad_datos.py`. Tiene una función pura `clasificar(filas_bronze, paises)` que devuelve las filas de Silver, las de rechazados y las métricas, y no toca Databricks. También tiene la parte que lee Bronze y `ref_paises` y escribe:
  - `DELETE` + `INSERT` en rechazados;
  - `INSERT OVERWRITE` en Silver solo si no se supera el umbral.

  Publica métricas y un resumen en el job.
- [ ] **5.2** Crear `tests/test_calidad_datos.py`, con el CSV real como si fuera la carga de Bronze:
  - 12 filas en Silver (con sus `customer_id`), 10 contactables y 2 menores;
  - 9 rechazados con sus motivos;
  - `registro_original` con los valores crudos y acentos sin escapar;
  - Silver normalizada;
  - con ≥ 50 % no se escribe Silver pero sí los rechazados;
  - estados `exito`, `advertencia` y `fallo`;
  - el resumen no contiene `@`.

## Grupo 6 · Stage 5 · Gold

- [ ] **6.1** Crear `sql/transformaciones/gold_contactables_pais.sql`: un `INSERT OVERWRITE` con `:run_id`, clientes únicos desde Bronze, `ZZ` para sin país o país desconocido, contactables desde Silver y nombre y región desde `ref_paises`.
- [ ] **6.2** Crear `scripts/calcular_gold.py`:
  - ejecuta el SQL;
  - comprueba que `SUM(clientes_unicos)` y `SUM(clientes_contactables)` cuadran con Bronze y Silver de la ejecución;
  - calcula el KPI global y su diferencia con la meta del 80 %;
  - publica métricas y un resumen.
- [ ] **6.3** Crear `tests/test_gold_sql.py`, con revisiones estáticas del SQL:
  - usa `INSERT OVERWRITE`, `:run_id` y `ZZ`, `Sin país` y `Sin región`;
  - no menciona `email`;
  - deduplica por `_row_number`.

  Agregar también tests del cálculo del KPI y de la comprobación de sumas, con un cursor falso.

## Grupo 7 · Stage 6 · Monitoreo

- [ ] **7.1** Crear `scripts/registrar_monitoreo.py`. Tiene una función pura que, a partir del JSON de `needs`, el evento y el SHA, arma las 6 filas: estado por resultado del job, stages que no corrieron, métricas que faltan y `trigger`. También tiene la parte que borra y escribe el `run_id` en Databricks y verifica que haya 6 filas. Termina en rojo si algún stage no terminó en `success`.
- [ ] **7.2** Crear `tests/test_monitoreo.py`. Casos:
  - todo en verde, con advertencias;
  - el stage 1 falla y el resto no corre;
  - un job sin métricas;
  - la traducción de `trigger`;
  - el `run_id` del stage 3 tiene prioridad;
  - el código de salida es `1` si algún stage falló;
  - ningún `mensaje` contiene `@`.

## Grupo 8 · Workflow

- [ ] **8.1** Modificar `.github/workflows/pipeline.yml`:
  - agregar `schedule` (`cron: "0 11 * * 1"`);
  - subir a `actions/checkout@v5` y `actions/setup-python@v6`;
  - cada job declara la salida `metricas`, e Ingesta también la salida `run_id`.
- [ ] **8.2** Agregar los jobs **`Ingesta a Bronze`**, **`Calidad de datos`** y **`Gold`**, encadenados con `needs`. Los dos últimos reciben `RUN_ID` desde la salida de la ingesta.
- [ ] **8.3** Agregar el job **`Monitoreo`**, con `needs` de los 5 jobs e `if: always()`. Recibe `toJSON(needs)` como variable de entorno.

## Grupo 9 · Documentación

- [ ] **9.1** Actualizar `README.md` → "Scripts del pipeline". Debe incluir:
  - los nuevos scripts y su stage;
  - los disparadores (PR, lunes 6:00 de Lima y manual);
  - cómo reactivar el schedule después de 60 días;
  - la diferencia entre *Re-run all jobs* y *Re-run failed jobs*;
  - las fechas en UTC;
  - un apartado **"Listo para ejecutar"**: fork, schema `demo`, 3 secrets y listo.

## Grupo 10 · Configuración de GitHub (la hace la persona, o el asistente con su autorización)

- [ ] **10.1** Después de la primera ejecución, agregar **`Ingesta a Bronze`**, **`Calidad de datos`**, **`Gold`** y **`Monitoreo`** como checks obligatorios en `proteger-main`. Quedan 6 en total.

## Grupo 11 · Pull Request y validación

- [ ] **11.1** Correr `pytest` en local, todo en verde.
- [ ] **11.2** Commit en la rama (`feat: fase 2 según spec`), push y Pull Request hacia `main` del fork, **sin hacer merge**.
- [ ] **11.3** Comprobar que los 6 stages corren en orden y terminan en verde, con advertencias en el shift-left y en calidad.
- [ ] **11.4** *Re-run all jobs* para comprobar la idempotencia.
- [ ] **11.5** Ejecutar manualmente el workflow sobre la rama (*Run workflow*) para comprobar el disparador manual y el valor `manual` en `trigger`.
- [ ] **11.6** Recorrer [validacion.md](validacion.md), marcar cada casilla y, si todo cumple, hacer merge a `main`.
