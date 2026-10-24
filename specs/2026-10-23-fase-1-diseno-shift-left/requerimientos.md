# Fase 1 · Diseño y calidad shift-left · Requerimientos

> Feature spec de la Fase 1 del [roadmap](../../constitucion/roadmap.md). Se apoya en la [misión](../../constitucion/mision.md) y el [stack tecnológico](../../constitucion/stack-tecnologico.md). Rama: `feat/fase-1-diseno-shift-left`.

## Scope

### Qué construye esta fase
1. Los **scripts SQL que crean las 6 tablas** del modelo en `workspace.demo`: `bronze_customers`, `silver_customers`, `rechazados_customers`, `ref_paises`, `gold_contactables_pais` y `monitoreo_ejecuciones`.
2. El **CSV de referencia de países** (`data/reference/paises.csv`) y su carga idempotente en `ref_paises`.
3. Un **contrato del modelo** (`sql/contrato_modelo.json`) con las tablas, columnas y tipos esperados, que el despliegue usa para verificar que todo quedó creado.
4. El **validador shift-left** en Python: chequeos estructurales que bloquean y reglas por fila que solo se reportan. Las reglas quedan en un módulo propio para que la Fase 2 las reutilice.
5. **Tests automáticos** (pytest) del validador.
6. El **workflow de GitHub Actions** con dos stages: **1 · Calidad shift-left** y **2 · Despliegue del modelo**.
7. El script de **permisos** (`sql/permisos.sql`), documentado pero no ejecutado por el pipeline.
8. La **documentación de cada script** en el `README.md`.

### Qué NO construye esta fase
- Ingesta a Bronze, transformación a Silver, cálculo de Gold ni inserción en rechazados: las tablas quedan **creadas y vacías** (salvo `ref_paises`).
- Registro en la tabla de monitoreo (la tabla se crea, pero se llena desde la Fase 2).
- Umbral de rechazos que haga fallar el pipeline (Fase 2).
- Carga programada de los lunes (Fase 2).
- Ejecución de los `GRANT` de permisos.

## Datos de entrada

### Archivo de origen: `data/source/customers.csv`

| Propiedad | Valor esperado |
|---|---|
| Codificación | UTF-8 (con o sin BOM) |
| Separador | Coma (`,`) |
| Encabezado | Exactamente `customer_id,name,age,country,email`, en ese orden |
| Filas de datos | Al menos 1 |

| Columna | Tipo lógico | Nota |
|---|---|---|
| `customer_id` | Texto | Identificador del CRM (ej. `C001`) |
| `name` | Texto | Nombre completo |
| `age` | Entero | Llega como texto; puede venir vacío o no numérico |
| `country` | Texto, 2 letras | Código de país (PE, CL, CO, MX, AR) |
| `email` | Texto | **Dato personal** |

### Referencia: `data/reference/paises.csv`

```csv
country_code,country_name,region
PE,Perú,Sudamérica
CL,Chile,Sudamérica
CO,Colombia,Sudamérica
AR,Argentina,Sudamérica
MX,México,Norteamérica
```

Solo contiene países reales. El agrupador "Sin país" de Gold **no** vive en esta tabla (ver [decisiones](#decisiones-tomadas)).

## Datos de salida

Todas las tablas son Delta, viven en `workspace.demo` y se crean desde los scripts de `sql/ddl/`. En los scripts, el catálogo y el schema se escriben como `{{catalog}}.{{schema}}`. El script de despliegue los reemplaza por `workspace` y `demo`, valores por defecto que no son secretos. Así el repo sigue corriendo solo con los 3 secrets, y el destino se puede cambiar sin tocar el SQL.

Reglas comunes a todos los scripts:
- `CREATE TABLE IF NOT EXISTS`: correrlos dos veces no falla ni borra datos.
- Comentario en cada tabla y en cada columna. Las columnas con email dicen `Dato personal (PII)` en su comentario.
- Nunca `DROP TABLE`. Los cambios futuros al modelo van en scripts nuevos numerados (`07_...`, `08_...`).

### `sql/ddl/01_bronze_customers.sql`

```sql
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
```

### `sql/ddl/02_silver_customers.sql`

```sql
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
```

### `sql/ddl/03_rechazados_customers.sql`

```sql
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
```

### `sql/ddl/04_ref_paises.sql`

```sql
CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}.ref_paises (
  country_code  STRING NOT NULL COMMENT 'Código ISO de 2 letras',
  country_name  STRING NOT NULL COMMENT 'Nombre del país',
  region        STRING NOT NULL COMMENT 'Región del país'
)
USING DELTA
COMMENT 'Referencia de países: código, nombre y región. Se carga desde data/reference/paises.csv';
```

### `sql/ddl/05_gold_contactables_pais.sql`

```sql
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
```

### `sql/ddl/06_monitoreo_ejecuciones.sql`

```sql
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
```

> `trigger` va entre comillas invertidas porque es palabra reservada en SQL.

### Carga de `ref_paises`

El script de despliegue lee `data/reference/paises.csv` y ejecuta un `MERGE` **parametrizado** (sin concatenar texto en el SQL), fila por fila o en un solo bloque:

```sql
MERGE INTO {{catalog}}.{{schema}}.ref_paises AS t
USING (SELECT :country_code AS country_code, :country_name AS country_name, :region AS region) AS s
ON t.country_code = s.country_code
WHEN MATCHED THEN UPDATE SET t.country_name = s.country_name, t.region = s.region
WHEN NOT MATCHED THEN INSERT (country_code, country_name, region)
  VALUES (s.country_code, s.country_name, s.region);
```

Correrlo dos veces deja las mismas 5 filas.

### Contrato del modelo: `sql/contrato_modelo.json`

Lista cada tabla con sus columnas y tipos, tal como aparecen en `information_schema.columns` (`STRING`, `INT`, `BIGINT`, `BOOLEAN`, `TIMESTAMP`, `DECIMAL(5,2)`). Después de ejecutar los DDL, el despliegue consulta `{{catalog}}.information_schema.columns` filtrando por el schema y **falla** si falta una tabla, falta una columna o un tipo no coincide. Columnas extra no fallan, pero se reportan como advertencia.

### Permisos: `sql/permisos.sql`

Implementa la matriz de [quién puede ver qué](../../constitucion/stack-tecnologico.md#quién-puede-ver-qué) con `GRANT SELECT ON TABLE ... TO <grupo>`, usando los grupos `marketing`, `bi`, `gobierno` e `ingenieria`. **No lo ejecuta el pipeline**, porque esos grupos no existen en Free Edition. Queda versionado y documentado en el README para un workspace real.

## Reglas de calidad

### Normalización antes de evaluar
- Se quitan los espacios al inicio y al final de **todos** los campos.
- `country` se pasa a mayúsculas.
- No se corrige nada más.

### Chequeos estructurales: **bloquean** el Pull Request

| Chequeo | Falla si… |
|---|---|
| Archivo existe | No existe `data/source/customers.csv` |
| Codificación | El archivo no se puede leer como UTF-8 |
| Encabezado | No es exactamente `customer_id,name,age,country,email`, en ese orden |
| Filas de datos | Solo tiene encabezado o está vacío |
| Forma de cada fila | Una fila no tiene exactamente 5 campos |

### Reglas por fila: en esta fase **solo se reportan** (advertencia)

La Fase 2 usará exactamente estas reglas para mandar filas a `rechazados_customers`.

| Regla | Motivo | Condición (después de normalizar) |
|---|---|---|
| ID vacío | `customer_id_vacio` | `customer_id` vacío |
| Nombre vacío | `nombre_vacio` | `name` vacío (incluye filas con solo espacios) |
| Edad vacía | `edad_vacia` | `age` vacío |
| Edad no numérica | `edad_no_numerica` | `age` no es un entero (`^-?\d+$`) |
| Edad fuera de rango | `edad_fuera_de_rango` | `age` entero fuera de 0 a 120 |
| País vacío | `pais_vacio` | `country` vacío |
| País desconocido | `pais_desconocido` | `country` no está en `data/reference/paises.csv` |
| Email vacío | `email_vacio` | `email` vacío |
| Email inválido | `email_invalido` | `email` no cumple `^[^@\s]+@[^@\s]+\.[^@\s]+$` |
| Duplicado | `duplicado` | Su `customer_id` (no vacío) ya apareció en una fila anterior. **Manda la primera fila**; las siguientes son duplicado, aunque la primera tenga otros errores |

- Si una fila tiene varios errores, se registran **todos** los motivos, separados por `; `, en el orden de la tabla.
- Las reglas de edad son excluyentes entre sí: solo aplica una de `edad_vacia`, `edad_no_numerica` o `edad_fuera_de_rango`.
- Lo mismo para país (`pais_vacio` o `pais_desconocido`) y para email (`email_vacio` o `email_invalido`).

### Menores de edad: **información**, no error
Una fila válida con `age < 18` no es un error de calidad. El reporte la cuenta aparte como "menores de edad (no contactables)".

### Porcentaje de filas con error
```
% filas con error = filas con al menos un motivo / filas de datos del archivo × 100
```
En la Fase 1 se reporta. En la Fase 2 hará fallar el stage de calidad si llega al 50 %.

### Reporte del stage shift-left
- Se escribe en el **resumen del job** de GitHub Actions (`GITHUB_STEP_SUMMARY`): total de filas, IDs únicos, filas con error y su %, conteo por motivo, menores de edad y una tabla con `número de fila`, `customer_id` y `motivos`.
- Si hay filas con error, el job emite una **advertencia** (`::warning::`) visible en el Pull Request, pero termina en verde.
- **Nunca muestra emails** ni la fila completa: solo `customer_id`, número de fila y motivos.

## Restricciones

### Seguridad
- Las credenciales se leen **solo** de variables de entorno que el workflow toma de GitHub Secrets (`DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`). Nunca se escriben en archivos, logs ni mensajes de error.
- Solo el stage 2 recibe los secrets. El stage 1 no los necesita y no los tiene.
- El workflow corre con permisos mínimos (`permissions: contents: read`).
- En el repo se activan **Secret scanning** y **Push protection** de GitHub, y `.env` sigue en `.gitignore`.
- Ningún log, reporte ni mensaje de error muestra emails.

### Datos personales
- El email existe en Bronze, Silver y en `registro_original` de rechazados, y lo marca el comentario de su columna. Gold no tiene ninguna columna con email.

### Costo
- Solo el SQL Warehouse serverless existente. No hay clusters ni jobs.
- El stage 1 no toca Databricks. Si falla, el stage 2 no corre y el warehouse no se enciende.

### Idempotencia
- Los DDL usan `CREATE TABLE IF NOT EXISTS`.
- `ref_paises` se carga con `MERGE` por `country_code`.
- Correr el workflow dos veces seguidas deja el mismo resultado, sin errores.

### Trazabilidad
- Cada ejecución tiene `run_id` = `<github.run_id>-<github.run_attempt>`, y el script de despliegue lo imprime en el log.
- El registro en `monitoreo_ejecuciones` empieza en la Fase 2. En la Fase 1, la trazabilidad queda en el historial de GitHub Actions.
- Un solo pipeline a la vez sobre el schema: `concurrency` del workflow con un grupo fijo y sin cancelar la ejecución en curso.

### Dependencias
- Python 3.11.
- `requirements.txt` con versiones fijadas: `databricks-sql-connector` y `pytest`.
- El CSV se lee con la librería estándar `csv`. No se usa pandas.

## Workflow: `.github/workflows/pipeline.yml`

| Propiedad | Valor |
|---|---|
| Disparadores | `pull_request` hacia `main` y `workflow_dispatch` |
| Concurrencia | Grupo `databricks-workspace-demo`, `cancel-in-progress: false` |
| Job 1 | Nombre visible **`Calidad shift-left`**: instala dependencias, corre `pytest` y luego `scripts/validar_csv.py` |
| Job 2 | Nombre visible **`Despliegue del modelo`**: `needs` el job 1, recibe los 3 secrets como variables de entorno y corre `scripts/desplegar_modelo.py` |

Los nombres visibles de los jobs son los que se marcan como checks obligatorios en el ruleset de `main`.

## Estructura de archivos de esta fase

```
data/reference/paises.csv
sql/ddl/01_bronze_customers.sql
sql/ddl/02_silver_customers.sql
sql/ddl/03_rechazados_customers.sql
sql/ddl/04_ref_paises.sql
sql/ddl/05_gold_contactables_pais.sql
sql/ddl/06_monitoreo_ejecuciones.sql
sql/contrato_modelo.json
sql/permisos.sql
scripts/reglas_calidad.py      ← reglas por fila (las reutiliza la Fase 2)
scripts/validar_csv.py         ← stage 1
scripts/db.py                  ← conexión a Databricks desde variables de entorno
scripts/desplegar_modelo.py    ← stage 2
tests/test_validar_csv.py
tests/test_reglas_calidad.py
tests/test_contrato.py
tests/test_db.py
tests/fixtures/*.csv
requirements.txt
.github/workflows/pipeline.yml
README.md                      ← sección "Scripts del pipeline"
```

## Decisiones tomadas

| Decisión | Motivo |
|---|---|
| Se crean las 6 tablas en la Fase 1, aunque 5 quedan vacías | El modelo completo se despliega y se valida desde el código antes de llenarlo, y la Fase 2 solo agrega lógica |
| El encabezado debe ser exacto y en orden | Es un contrato con el CRM: cualquier cambio de estructura debe detectarse en el PR, no en producción |
| Los errores por fila solo dan advertencia en la Fase 1 | Todavía no existen la ingesta ni la tabla de rechazados que los procesen. Bloquear impediría mergear con el dato actual |
| Las reglas viven en `scripts/reglas_calidad.py` | La Fase 2 aplica las mismas reglas en el stage de calidad: una sola fuente de verdad |
| Se guardan todos los motivos de una fila | Quien corrige en el CRM ve todos los problemas de una vez |
| La primera fila manda en duplicados, aunque tenga errores | Decisión de clase: es una regla simple y predecible. Con ella el resultado no depende de qué otros errores tenga cada fila |
| Solo se quitan espacios y se pasa el país a mayúsculas | Son correcciones sin ambigüedad. Cualquier otra corrección cambiaría el dato del CRM sin que nadie lo sepa |
| "Sin país" (`ZZ`) solo existe en Gold, no en `ref_paises` | Si estuviera en la referencia, la regla `pais_desconocido` lo daría por válido |
| `{{catalog}}.{{schema}}` en los DDL, con valores por defecto | El repo corre solo con los 3 secrets y el destino se puede cambiar sin editar SQL |
| `MERGE` parametrizado para `ref_paises` | Idempotente y sin riesgo de inyección SQL |
| Contrato del modelo en JSON y verificado contra `information_schema` | Comprueba de forma automática que lo creado coincide con lo especificado |
| `permisos.sql` versionado pero no ejecutado | En Free Edition no existen los grupos. La matriz queda lista para un workspace real |
| Edad válida de 0 a 120 | Rango amplio que solo atrapa valores imposibles. Los menores se manejan con la bandera, no con el rango |
