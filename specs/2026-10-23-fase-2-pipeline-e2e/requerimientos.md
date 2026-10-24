# Fase 2 · Pipeline de punta a punta · Requerimientos

> Feature spec de la Fase 2 del [roadmap](../../constitucion/roadmap.md). Se apoya en la [misión](../../constitucion/mision.md), el [stack tecnológico](../../constitucion/stack-tecnologico.md) y lo construido en la [Fase 1](../2026-10-23-fase-1-diseno-shift-left/requerimientos.md). Rama: `feat/fase-2-pipeline-e2e`.

## Scope

### Qué construye esta fase
1. **Stage 3 · Ingesta a Bronze**: el CSV crudo a `bronze_customers`, con `_run_id`, archivo de origen y número de fila.
2. **Stage 4 · Calidad de datos**: aplica `scripts/reglas_calidad.py` a la carga de Bronze. Los válidos van a `silver_customers` y los rechazados a `rechazados_customers`, con su motivo. Falla con **50 % o más** de rechazos.
3. **Stage 5 · Gold**: `gold_contactables_pais` con nombre del país, región e indicador de contactables, sin datos personales. Incluye la fila `ZZ` · "Sin país".
4. **Stage 6 · Monitoreo**: un job final que **corre siempre** y escribe en `monitoreo_ejecuciones` una fila por stage, incluida la suya.
5. **Shift-left ampliado**: el stage 1 **bloquea** el PR si las filas con error llegan al 50 %, antes de tocar Databricks.
6. **Carga programada** los lunes a las 6:00 a. m. hora de Lima, sobre `main`, más la ejecución manual que ya existe.
7. **Mejoras pendientes de la Fase 1**:
   - el `MERGE` de `ref_paises` solo actualiza si algo cambió;
   - `actions/checkout` y `actions/setup-python` suben a versiones con Node 24.
8. **README final**: el repo corre de punta a punta solo con los 3 secrets.

### Qué NO construye esta fase
- Alertas por Slack o Teams (las notificaciones de GitHub son el canal).
- Ambientes separados de desarrollo y producción.
- Ejecución de `sql/permisos.sql`.
- Retención o limpieza de la historia de Bronze, rechazados y monitoreo.
- Dashboards ni visualizaciones.

### Ajuste a la constitución (aprobado)
[stack-tecnologico.md](../../constitucion/stack-tecnologico.md) decía que las transformaciones Bronze → Silver → Gold se hacían en SQL. Se actualizó a: **Python para las reglas de calidad (Bronze → Silver + rechazados) y SQL para DDL y Gold**. Así las reglas tienen una sola fuente de verdad, la misma que usa el shift-left. También se actualizó la descripción del stage 6: un job final escribe el monitoreo de todos los stages.

## Identificador de ejecución (`run_id`)

- `run_id` = `<github.run_id>-<github.run_attempt>`, como en la Fase 1.
- El stage 3 publica el `run_id` con el que cargó Bronze, y **los stages 4, 5 y 6 usan ese mismo valor**. Así, si alguien usa *Re-run failed jobs*, calidad y Gold leen la carga correcta de Bronze. Si el stage 3 no corrió, el monitoreo usa el `run_id` del intento actual.
- *Re-run all jobs* genera un `run_id` nuevo: es una ejecución nueva, con su propia tanda en Bronze, rechazados y monitoreo.

## Stage 1 · Calidad shift-left (cambia)

Todo lo de la Fase 1 se mantiene, y se agrega:
- **Bloquea** (código `1`) si `% filas con error >= 50`. El umbral es una constante única, `UMBRAL_RECHAZO_PCT = 50`, en `scripts/reglas_calidad.py`, y la usan el stage 1 y el stage 4.
- Por debajo del umbral, con al menos una fila con error: advertencia, como hasta ahora.
- El texto del reporte ya no dice "en la Fase 1 no bloquean". Ahora indica el umbral y si se superó.
- Publica sus métricas para el monitoreo (ver [Métricas de cada stage](#métricas-de-cada-stage)).
- Sigue **sin secrets** y **sin tocar Databricks**.

## Stage 2 · Despliegue del modelo (cambia)

- El `MERGE` de `ref_paises` solo actualiza cuando cambió el nombre o la región:
  ```sql
  WHEN MATCHED AND (t.country_name <> s.country_name OR t.region <> s.region) THEN UPDATE SET ...
  ```
  Una segunda ejecución con el mismo CSV no escribe nada (`numTargetRowsUpdated = 0`).
- Nuevo script `sql/ddl/07_comentario_stage_monitoreo.sql`, que agrega `monitoreo` a los valores posibles de la columna `stage`. Es un cambio solo de comentario, sin `DROP` y repetible:
  ```sql
  ALTER TABLE {{catalog}}.{{schema}}.monitoreo_ejecuciones
    ALTER COLUMN stage COMMENT 'shift_left | despliegue_modelo | bronze | calidad | gold | monitoreo';
  ```
  El contrato del modelo no cambia: no hay columnas ni tipos nuevos.
- Publica sus métricas para el monitoreo: `filas_salida` = filas en `ref_paises`.

## Stage 3 · Ingesta a Bronze

| | |
|---|---|
| Script | `scripts/ingestar_bronze.py` |
| Entrada | `data/source/customers.csv` (ya validado por el stage 1) |
| Salida | `bronze_customers`, filas con `_run_id` = el de esta ejecución |

Reglas:
- Lee el archivo con los mismos chequeos estructurales del stage 1 (reutiliza `validar_csv.leer_filas`).
- Los 5 campos entran **tal cual**: sin quitar espacios ni corregir nada. Bronze es el dato crudo.
- `_source_file` = `data/source/customers.csv` · `_row_number` = 1, 2, … en el orden del archivo · `_ingested_at` = `current_timestamp()` (UTC).
- Idempotente para la misma ejecución: primero `DELETE FROM bronze_customers WHERE _run_id = :run_id` y luego el `INSERT`.
- El `INSERT` es **parametrizado** (marcadores `:nombre`), por lotes, nunca concatenando valores en el SQL.
- Después del `INSERT`, cuenta las filas con ese `_run_id`. **Falla** si no coinciden con las filas de datos del archivo.
- Publica el `run_id` como salida del job, para los stages siguientes.
- El log muestra solo conteos. Nunca filas ni emails.

## Stage 4 · Calidad de datos

| | |
|---|---|
| Script | `scripts/calidad_datos.py` |
| Entrada | `bronze_customers` donde `_run_id` = el del stage 3, en orden de `_row_number` · `ref_paises` (códigos válidos) |
| Salida | `silver_customers` (reemplazo completo) · `rechazados_customers` (filas de esta ejecución) |

Reglas:
- Evalúa las filas con `reglas_calidad.evaluar_filas`, las mismas reglas, motivos y orden de la Fase 1. Los códigos de país válidos se leen de la tabla `ref_paises`.
- **Rechazados**: una fila por cada fila con al menos un motivo.

  | Columna | Valor |
  |---|---|
  | `_run_id` | El de la ejecución |
  | `_row_number` | El de Bronze |
  | `customer_id` | Tal como llegó, sin espacios al inicio ni al final. `NULL` si venía vacío |
  | `registro_original` | JSON con los 5 campos **crudos** de Bronze (`customer_id`, `name`, `age`, `country`, `email`), sin escapar acentos (`ensure_ascii=False`) |
  | `motivo` | Todos los motivos separados por `; ` |
  | `_rejected_at` | `current_timestamp()` (UTC) |

  Idempotente para la misma ejecución: primero `DELETE ... WHERE _run_id = :run_id`, luego `INSERT` parametrizado.
- **Silver**: las filas válidas, **normalizadas**:
  - `customer_id` y `name` sin espacios al inicio ni al final;
  - `age` como `INT`;
  - `country_code` en mayúsculas;
  - `email` sin espacios;
  - `es_mayor_edad` = `age >= 18`;
  - `es_contactable` = `es_mayor_edad`, porque toda fila de Silver ya es válida;
  - `_processed_at` = `current_timestamp()`.

  Se escribe con **`INSERT OVERWRITE`** parametrizado: Silver queda solo con la carga de esta ejecución.
- **Umbral** (`% = filas rechazadas / filas de Bronze de la ejecución × 100`):

  | Rechazos | Rechazados | Silver | Estado | Stage |
  |---|---|---|---|---|
  | 0 | — | Se reemplaza | `exito` | Verde |
  | ≥ 1 y < 50 % | Se guardan | Se reemplaza | `advertencia` + `::warning::` | Verde |
  | ≥ 50 % | **Se guardan**, para revisar | **No se toca**: queda la última carga buena | `fallo` + `::error::` | **Rojo**: Gold no corre |
- Escribe en el resumen del job: filas leídas, válidas, rechazadas, %, menores de edad y conteo por motivo. Nunca emails.

## Stage 5 · Gold

| | |
|---|---|
| Script | `scripts/calcular_gold.py`, que ejecuta `sql/transformaciones/gold_contactables_pais.sql` |
| Entrada | `bronze_customers` (la carga de la ejecución) · `silver_customers` · `ref_paises` |
| Salida | `gold_contactables_pais` (reemplazo completo) |

Lógica del SQL (un solo `INSERT OVERWRITE`, con `:run_id` como parámetro):
1. **Clientes únicos**: de Bronze de la ejecución, `customer_id` sin espacios y no vacío. Ante un repetido, manda la fila con menor `_row_number` (la misma regla de duplicados).
2. **País de cada cliente único**: `upper(trim(country))`. Si está vacío o no existe en `ref_paises`, va a `ZZ`.
3. **Contactables**: filas de Silver con `es_contactable = true` y `_run_id` de la ejecución, por `country_code`.
4. **Una fila por país** con al menos un cliente único:
   - `country_name` y `region` salen de `ref_paises`; para `ZZ`, "Sin país" y "Sin región";
   - `pct_contactables` = `ROUND(100 × contactables / únicos, 2)` como `DECIMAL(5,2)`;
   - `_run_id` y `_updated_at` = `current_timestamp()`.
5. La fila `ZZ` **solo aparece si hay al menos un cliente** sin país o con país desconocido.

Comprobaciones del script después del `INSERT OVERWRITE` (si alguna falla, el stage falla):
- `SUM(clientes_unicos)` = clientes únicos de Bronze de la ejecución.
- `SUM(clientes_contactables)` = filas contactables de Silver de la ejecución.
- Ninguna columna de Gold contiene emails (la verificación del contrato de la Fase 1 sigue vigente).

El script escribe el **KPI global** en el log y en el resumen del job:
```
% contactables = SUM(clientes_contactables) / SUM(clientes_unicos) × 100
```
También muestra la meta (80 %) y la diferencia con ella.

## Stage 6 · Monitoreo

| | |
|---|---|
| Script | `scripts/registrar_monitoreo.py` |
| Cuándo corre | Siempre (`if: always()`), después de los stages 1 a 5, aunque alguno haya fallado o no haya corrido |
| Entrada | Resultado y métricas de cada job (`toJSON(needs)` del workflow) |
| Salida | `monitoreo_ejecuciones`: **6 filas** por ejecución (`shift_left`, `despliegue_modelo`, `bronze`, `calidad`, `gold`, `monitoreo`) |

Reglas:
- Idempotente para la misma ejecución: `DELETE ... WHERE run_id = :run_id` y luego `INSERT` parametrizado de las 6 filas.
- `estado` por stage:
  - si el job terminó en `success`, se usa el estado que publicó el stage (`exito` o `advertencia`);
  - si terminó en `failure` o `cancelled`, queda `fallo`;
  - si no corrió (`skipped`) porque falló un stage anterior, queda `fallo`, con `mensaje` = "No corrió: falló un stage anterior".
- Si un job falló antes de publicar métricas, las filas quedan en `NULL` y `started_at` toma la hora del monitoreo. El `mensaje` lo explica.
- `trigger`: `pull_request` → `pull_request`; `schedule` → `schedule`; `workflow_dispatch` → `manual`.
- `git_sha` = `GITHUB_SHA`.
- Después de escribir, cuenta las filas del `run_id`. **Falla** si no son 6.
- **Termina en rojo** si algún stage del 1 al 5 no terminó en `success`, para que el monitoreo nunca oculte un fallo. El resumen del job muestra una tabla con el estado de cada stage.
- El `mensaje` nunca contiene emails.

## Métricas de cada stage

Cada script de los stages 1 a 5 publica, al terminar y también cuando falla (`try/finally`), una salida de job `metricas` con este JSON:

```json
{
  "stage": "calidad",
  "estado": "advertencia",
  "filas_entrada": 21,
  "filas_salida": 12,
  "filas_rechazadas": 9,
  "mensaje": "9 de 21 filas rechazadas (42,86 %)",
  "started_at": "2026-10-23T11:00:05Z",
  "finished_at": "2026-10-23T11:00:31Z"
}
```

Se escribe en `GITHUB_OUTPUT` con un módulo común (`scripts/metricas.py`). Fuera de GitHub Actions solo se imprime.

| Stage | `filas_entrada` | `filas_salida` | `filas_rechazadas` |
|---|---|---|---|
| `shift_left` | Filas del CSV | Filas sin error | Filas con error |
| `despliegue_modelo` | — | Filas en `ref_paises` | — |
| `bronze` | Filas del CSV | Filas en Bronze con el `run_id` | — |
| `calidad` | Filas de Bronze de la ejecución | Filas en Silver | Filas en rechazados |
| `gold` | Filas de Silver de la ejecución | Filas en Gold | — |
| `monitoreo` | Stages evaluados (5) | Filas escritas (6) | Stages que no terminaron en verde |

## Workflow: `.github/workflows/pipeline.yml` (cambia)

| Propiedad | Valor |
|---|---|
| Disparadores | `pull_request` hacia `main` · `schedule: cron "0 11 * * 1"` (lunes 6:00 hora de Lima = 11:00 UTC) · `workflow_dispatch` |
| Permisos | `contents: read` |
| Concurrencia | Grupo `databricks-workspace-demo`, `cancel-in-progress: false` |
| Acciones | `actions/checkout@v5` y `actions/setup-python@v6` (Node 24) |

| Job (nombre visible = check obligatorio) | `needs` | Secrets | Script |
|---|---|---|---|
| `Calidad shift-left` | — | No | `pytest` + `scripts/validar_csv.py` |
| `Despliegue del modelo` | shift-left | Sí | `scripts/desplegar_modelo.py` |
| `Ingesta a Bronze` | despliegue | Sí | `scripts/ingestar_bronze.py` |
| `Calidad de datos` | ingesta | Sí | `scripts/calidad_datos.py` |
| `Gold` | calidad | Sí | `scripts/calcular_gold.py` |
| `Monitoreo` | los 5 anteriores, `if: always()` | Sí | `scripts/registrar_monitoreo.py` |

- Los secrets solo se pasan como variables de entorno al paso que ejecuta el script.
- **Schedule en repos públicos**: GitHub desactiva los schedules después de 60 días sin actividad en el repo. El README explica cómo reactivarlo (*Actions → Pipeline ClientesConfiables → Enable workflow*).
- **Alertas**: si el workflow falla, GitHub notifica por correo. En las ejecuciones programadas notifica a quien modificó el `cron` por última vez.

## Restricciones

### Seguridad y datos personales
- Credenciales solo desde GitHub Secrets. El stage 1 no los recibe.
- Todo SQL con valores de datos es **parametrizado**.
- Ningún log, resumen de job ni `mensaje` de monitoreo muestra emails ni filas completas. Lo comprueban tests automáticos.
- El email solo existe en Bronze, Silver y en `registro_original` de rechazados. **Gold no tiene emails**.

### Idempotencia
- Para la misma ejecución (`run_id`), cada stage borra lo suyo antes de insertar: Bronze, rechazados y monitoreo.
- Silver y Gold se reemplazan completos (`INSERT OVERWRITE`).
- Una ejecución nueva agrega su tanda a Bronze, rechazados y monitoreo (es historia, no duplicación), y deja Silver y Gold con el mismo contenido si el archivo no cambió.

### Trazabilidad
- Cada fila de Bronze, Silver, Gold y rechazados tiene el `_run_id` de la ejecución que la generó.
- Cada ejecución deja 6 filas en `monitoreo_ejecuciones`, con `git_sha` y `trigger`.
- Todas las fechas son **UTC**. Para hora de Lima: `from_utc_timestamp(col, 'America/Lima')`.

### Costo
- Solo el SQL Warehouse serverless.
- Si el stage 1 falla, del 2 al 5 no corren. El monitoreo sí corre y enciende el warehouse unos segundos para registrar el fallo (decisión aceptada a cambio de la trazabilidad).

### Dependencias
- Sin dependencias nuevas: `databricks-sql-connector` y `pytest`, con las versiones fijadas en la Fase 1.

## Estructura de archivos de esta fase

```
scripts/metricas.py                       ← nuevo: publica las métricas del stage
scripts/ingestar_bronze.py                ← nuevo: stage 3
scripts/calidad_datos.py                  ← nuevo: stage 4
scripts/calcular_gold.py                  ← nuevo: stage 5
scripts/registrar_monitoreo.py            ← nuevo: stage 6
sql/transformaciones/gold_contactables_pais.sql   ← nuevo
sql/ddl/07_comentario_stage_monitoreo.sql         ← nuevo
scripts/reglas_calidad.py                 ← cambia: UMBRAL_RECHAZO_PCT
scripts/validar_csv.py                    ← cambia: bloquea con ≥ 50 %, publica métricas
scripts/desplegar_modelo.py               ← cambia: MERGE condicional, scripts ALTER, métricas
tests/test_metricas.py                    ← nuevo
tests/test_ingesta_bronze.py              ← nuevo
tests/test_calidad_datos.py               ← nuevo
tests/test_gold_sql.py                    ← nuevo
tests/test_monitoreo.py                   ← nuevo
tests/fixtures/mayoria_con_error.csv      ← nuevo
tests/test_validar_csv.py, tests/test_contrato.py   ← cambian
.github/workflows/pipeline.yml            ← cambia
README.md                                 ← cambia
```

## Decisiones tomadas

| Decisión | Motivo |
|---|---|
| Reglas de calidad en Python, Gold en SQL (ajuste a la constitución) | Una sola fuente de verdad para las reglas, compartida con el shift-left. Gold es una agregación natural en SQL |
| El shift-left bloquea con ≥ 50 % | Raúl quiere encontrar los errores en el PR, antes de encender Databricks. Es el mismo umbral que el stage 4 |
| Los stages 4 a 6 usan el `run_id` que publica el stage 3 | *Re-run failed jobs* no deja a calidad leyendo una carga de Bronze que no existe |
| Bronze guarda el dato crudo, sin quitar espacios | Bronze es la evidencia de lo que llegó. La normalización ocurre al pasar a Silver |
| Con ≥ 50 %, se guardan los rechazados pero no se toca Silver | Gobierno puede revisar qué falló, y Marketing sigue con la última lista buena en vez de una lista vacía o a medias |
| `es_contactable = es_mayor_edad` en Silver | Solo los registros válidos (con email válido) llegan a Silver, así que contactable equivale a mayor de edad |
| Clientes únicos de Gold desde Bronze, contactables desde Silver | El denominador del KPI son todos los clientes únicos del archivo, incluidos los rechazados (constitución) |
| Fila `ZZ` "Sin país" solo en Gold y solo si hay casos | La suma de Gold cuadra con el KPI global sin agregar un país falso a `ref_paises` |
| Un job de monitoreo central que corre siempre | El stage 1 no toca Databricks, y un job que falla no siempre alcanza a escribir. El job central registra todo, también los stages que no corrieron |
| El monitoreo termina en rojo si algún stage falló | El registro nunca hace ver verde una ejecución con fallos |
| `MERGE` de países condicional | Una segunda ejecución sin cambios no reescribe archivos en Delta |
| Fechas en UTC | Es el estándar de Databricks y GitHub, y evita ambigüedad con cambios de horario |
| Schedule 6:00 de Lima (11:00 UTC) | 2 horas de margen antes de las 8:00, porque GitHub puede retrasar los schedules |
