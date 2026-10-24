# Stack tecnológico · ClientesConfiables

> Parte de la constitución del proyecto. Responde **¿cómo encaja con la tecnología?** y fija las restricciones de equipo, gobierno y calidad. Ninguna herramienta es obligatoria: lo que importa es la práctica que cubre. Si cambia una herramienta, se actualiza este archivo y las feature specs siguen sirviendo.

## Herramientas y alternativas

| Práctica | Herramienta elegida | Alternativa comercial | Alternativa open source |
|---|---|---|---|
| Almacenamiento y cómputo SQL | Databricks Free Edition · SQL Warehouse serverless | Snowflake, Google BigQuery | DuckDB, PostgreSQL, Spark + Trino |
| Formato de tablas | Delta Lake (por defecto en Databricks) | Formato nativo de Snowflake / BigQuery | Apache Iceberg, Apache Hudi |
| Orquestación y CI/CD | GitHub Actions | GitLab CI, Azure DevOps Pipelines | Jenkins, Apache Airflow, Dagster |
| Gestión de secretos | GitHub Secrets | Azure Key Vault, AWS Secrets Manager | HashiCorp Vault |
| Versionamiento | Git + GitHub (rama `main` protegida) | GitLab, Bitbucket | Gitea |
| Validación de calidad | Scripts en Python propios + pytest | Soda Cloud, Monte Carlo | Great Expectations, Soda Core, pandera |
| Conexión al warehouse | `databricks-sql-connector` (Python) | Drivers JDBC/ODBC del proveedor | SQLAlchemy |
| Gobierno y acceso | Unity Catalog (permisos por tabla) | Microsoft Purview, Collibra | OpenMetadata, DataHub |
| Monitoreo | Tabla de monitoreo en Databricks + notificaciones de GitHub | Datadog, Monte Carlo | Elementary, OpenTelemetry |

## Plataforma

- **Workspace:** Databricks Free Edition, propio del proyecto.
- **Catálogo y schema:** `workspace.demo`. Todas las tablas viven ahí.
- **Cómputo:** el SQL Warehouse serverless del workspace. Se apaga solo cuando no se usa; la primera consulta de cada ejecución puede tardar unos segundos más.
- **Conexión:** solo con los 3 secrets de GitHub (`DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`).

## Lenguajes

- **SQL** para crear tablas (DDL) y para la transformación Silver → Gold.
- **Python 3.11** para la validación shift-left, la ingesta del CSV, las reglas de calidad Bronze → Silver + rechazados (`scripts/reglas_calidad.py`, única fuente de verdad de las reglas, la misma que usa el shift-left), la ejecución de los scripts SQL y el registro de monitoreo. Dependencias mínimas: `databricks-sql-connector` y `pytest`. El CSV se lee con la librería estándar `csv`.

## Arquitectura medallion

```
customers.csv ──► Bronze ──► (calidad) ──┬──► Silver ──► Gold (por país)
                                         └──► Rechazados (con motivo)
ref_paises ─────────────────────────────────────────────┘
Cada stage ──► Monitoreo
```

| Capa | Para qué | Quién la consume |
|---|---|---|
| **Bronze** | Dato crudo tal como llega, sin transformar, con historia de cada ejecución | Ingeniería de Datos |
| **Silver** | Solo registros válidos, tipados y deduplicados, con banderas de negocio | Marketing (lista de campaña), Ingeniería |
| **Gold** | Indicador de contactables por país, con nombre y región, sin datos personales | BI, Marketing |
| **Rechazados** | Registros con error, el registro original y el motivo, para corregir en el origen | Gobierno de Datos, dueños del CRM |
| **Referencia de países** | Código → nombre del país y región | Gold |
| **Monitoreo** | Una fila por stage y por ejecución | Ingeniería, BI, Gobierno |

## Modelado

### Modelo lógico

- **Cliente** (`customer_id`) pertenece a un **País** (`country_code`). Relación N:1.
- **País** tiene un nombre y una **región**.
- **Ejecución** (`run_id`) carga N registros en Bronze, rechaza N registros y deja N registros de monitoreo (uno por stage).
- Cada **registro rechazado** viene de un registro de Bronze de una ejecución y tiene uno o más motivos.
- El **indicador por país** se calcula desde Silver, unido con la referencia de países, para una ejecución.

### Modelo físico

Todas las tablas son Delta en `workspace.demo` y se crean con scripts SQL versionados en el repo, **nunca a mano**. Los scripts usan `CREATE TABLE IF NOT EXISTS` (o `CREATE OR REPLACE` cuando la tabla se reconstruye completa) para que correrlos dos veces no falle ni duplique.

Las columnas que empiezan con `_` son técnicas, de trazabilidad.

**`bronze_customers`**: crudo, todo como texto; cada ejecución agrega sus filas identificadas por `_run_id`.

| Columna | Tipo | Nota |
|---|---|---|
| `customer_id` | STRING | Tal cual llega |
| `name` | STRING | Tal cual llega |
| `age` | STRING | Texto: puede venir vacío o no numérico |
| `country` | STRING | Tal cual llega |
| `email` | STRING | Dato personal |
| `_run_id` | STRING | Ejecución que cargó la fila |
| `_source_file` | STRING | Ruta del archivo de origen |
| `_row_number` | INT | Posición de la fila en el archivo (para saber cuál duplicado va primero) |
| `_ingested_at` | TIMESTAMP | Momento de la carga |

**`silver_customers`**: solo registros válidos de la última ejecución, un registro por `customer_id`.

| Columna | Tipo | Nota |
|---|---|---|
| `customer_id` | STRING | Clave única |
| `name` | STRING | Sin espacios al inicio ni al final |
| `age` | INT | |
| `country_code` | STRING | 2 letras, en mayúscula, existe en `ref_paises` |
| `email` | STRING | Dato personal, formato válido |
| `es_mayor_edad` | BOOLEAN | Derivada: `age >= 18` |
| `es_contactable` | BOOLEAN | Derivada: válido y mayor de edad |
| `_run_id` | STRING | |
| `_processed_at` | TIMESTAMP | |

**`rechazados_customers`**: historia de rechazos por ejecución.

| Columna | Tipo | Nota |
|---|---|---|
| `_run_id` | STRING | |
| `_row_number` | INT | Fila en el archivo de origen |
| `customer_id` | STRING | Puede venir vacío |
| `registro_original` | STRING | La fila completa, tal como llegó (JSON) |
| `motivo` | STRING | Uno o más motivos, legibles por una persona |
| `_rejected_at` | TIMESTAMP | |

**`ref_paises`**: se carga desde un CSV de referencia versionado en el repo.

| Columna | Tipo | Nota |
|---|---|---|
| `country_code` | STRING | PE, CL, CO, AR, MX |
| `country_name` | STRING | Perú, Chile, Colombia, Argentina, México |
| `region` | STRING | Sudamérica (PE, CL, CO, AR) · Norteamérica (MX) |

**`gold_contactables_pais`**: indicador por país, sin datos personales.

| Columna | Tipo | Nota |
|---|---|---|
| `country_code` | STRING | |
| `country_name` | STRING | |
| `region` | STRING | |
| `clientes_unicos` | BIGINT | Clientes únicos del origen en ese país |
| `clientes_contactables` | BIGINT | Solo mayores de edad y válidos |
| `pct_contactables` | DECIMAL(5,2) | |
| `_run_id` | STRING | |
| `_updated_at` | TIMESTAMP | |

**`monitoreo_ejecuciones`**: una fila por stage y por ejecución.

| Columna | Tipo | Nota |
|---|---|---|
| `run_id` | STRING | |
| `stage` | STRING | `shift_left`, `despliegue_modelo`, `bronze`, `calidad`, `gold`, `monitoreo` |
| `estado` | STRING | `exito`, `advertencia`, `fallo` |
| `filas_entrada` | BIGINT | |
| `filas_salida` | BIGINT | |
| `filas_rechazadas` | BIGINT | |
| `mensaje` | STRING | Detalle legible |
| `trigger` | STRING | `pull_request`, `schedule`, `manual` |
| `git_sha` | STRING | Commit que se ejecutó |
| `started_at` | TIMESTAMP | |
| `finished_at` | TIMESTAMP | |

> La spec de la Fase 1 puede ajustar columnas y tipos, y debe decidir cómo se agrupan en Gold los clientes sin país válido (por ejemplo, una fila "Sin país"), para que la suma de Gold cuadre con el KPI global.

## Versionamiento y ramas

- `main` está **protegida**: no acepta push directo ni force push, y solo recibe cambios por Pull Request.
- Cada fase del roadmap (y la constitución) se trabaja en su propia rama: `docs/...` para documentación y `feat/...` para fases.
- Solo se hace **merge a `main` cuando todos los stages del pipeline pasan en verde**. Los stages son checks obligatorios del ruleset de `main`.
- El Pull Request no necesita aprobación de otra persona (0 aprobaciones): lo que bloquea o deja pasar son los stages.
- Mensajes de commit con prefijo: `docs:`, `feat:`, `fix:`, `test:`, `ci:`.

## Pipeline por stages

Un solo workflow de GitHub Actions con un job por stage, encadenados: si un stage falla, los siguientes no corren y el Pull Request queda bloqueado.

| # | Stage | Qué hace | ¿Toca Databricks? | Bloquea si… |
|---|---|---|---|---|
| 1 | **Calidad shift-left** | Valida el CSV en el runner: columnas, encabezado, tipos y reglas de calidad | No | Falta una columna, el archivo está vacío o el encabezado está mal |
| 2 | **Despliegue del modelo** | Crea o actualiza las tablas desde los scripts SQL y carga `ref_paises` | Sí | Un script SQL falla |
| 3 | **Ingesta a Bronze** | Inserta el CSV crudo con el `run_id` de la ejecución | Sí | La carga falla o las filas cargadas no coinciden con las del archivo |
| 4 | **Calidad de datos** | Válidos → Silver; con error → rechazados, con motivo | Sí | Rechazos **≥ 50 %** de las filas leídas (con al menos 1 rechazo queda como advertencia) |
| 5 | **Gold** | Calcula el indicador por país con nombre y región, solo mayores de edad como contactables | Sí | El cálculo falla |
| 6 | **Monitoreo** | Cada stage publica sus métricas; este job corre siempre (también si algo falla) y escribe en `monitoreo_ejecuciones` una fila por stage, incluida la suya | Sí | Algún stage no terminó en verde o no se pudo escribir el registro (nunca oculta el fallo de un stage) |

### Cuándo corre

| Disparador | Rama | Stages |
|---|---|---|
| Pull Request hacia `main` | La rama de la fase | Todos |
| Programado: lunes 6:00 a. m. hora de Lima (`cron: "0 11 * * 1"`, UTC) | `main` | Todos |
| Manual (`workflow_dispatch`) | Cualquiera | Todos |

- Dos ejecuciones nunca corren a la vez sobre el schema (`concurrency` en el workflow), porque PRs y carga programada comparten `workspace.demo`.
- La carga programada de las 6:00 deja 2 horas de margen antes de las 8:00, porque GitHub puede retrasar los schedules.

### Listo para ejecutar

Al terminar las dos fases, el repo debe correr de punta a punta **solo con configurar los 3 secrets** de GitHub, en un workspace con el schema `demo`. Cada script se documenta en el `README.md`: qué hace y en qué stage corre.

## Restricciones de gobierno y calidad

### Datos personales
- El **email** es el único dato personal sensible del proyecto. Vive en Bronze, Silver y en el registro original de rechazados; **nunca en Gold**.
- Nunca se imprimen emails en los logs de GitHub Actions (los reportes de calidad muestran `customer_id` y motivo, no el email).

### Quién puede ver qué

| Tabla | Marketing | BI | Gobierno | Ingeniería |
|---|---|---|---|---|
| Bronze | — | — | ✔ | ✔ |
| Silver (con email) | ✔ | — | ✔ | ✔ |
| Gold | ✔ | ✔ | ✔ | ✔ |
| Rechazados | — | — | ✔ | ✔ |
| Monitoreo | — | ✔ | ✔ | ✔ |

En Databricks se implementa con permisos de Unity Catalog (`GRANT SELECT`) por grupo. En Free Edition hay un solo usuario, así que la matriz queda documentada y en el script de permisos, aunque no se pueda probar con varios grupos.

### Credenciales
- Las credenciales viven **solo en GitHub Secrets**. Nunca en el código, en archivos `.env` versionados, en logs ni en el chat con el asistente de IA.
- El token de Databricks tiene fecha de vencimiento y se renueva antes de que expire.

### Reglas mínimas de calidad
- Columnas obligatorias: `customer_id`, `name`, `age`, `country`, `email`.
- `name` no vacío (ni solo espacios).
- `age` numérica entera, en un rango razonable (el rango exacto lo fija la spec).
- `country` presente y existente en `ref_paises`.
- `email` presente y con formato válido.
- `customer_id` único: ante duplicados manda el primero del archivo.
- Menores de edad: **no son error**, pasan a Silver con `es_mayor_edad = false`.
- Las reglas exactas, los motivos de rechazo y su texto los define la spec de cada fase.

### Idempotencia
- Correr el pipeline dos veces con el mismo archivo **no duplica datos**.
- Bronze y rechazados guardan historia por `run_id`. Si se reintenta la misma ejecución, primero se borran las filas de ese `run_id` y luego se insertan.
- Silver y Gold se reconstruyen completas desde la última carga de Bronze.

### Trazabilidad
- `run_id` = `<github.run_id>-<github.run_attempt>`. Está en cada fila de Bronze, Silver, Gold y rechazados.
- Cada stage deja su registro en `monitoreo_ejecuciones` con el commit (`git_sha`) y el disparador.
- Si el pipeline falla, GitHub notifica por correo a quien lo disparó o a quien sigue el repo, y BI puede revisar la tabla de monitoreo.

### Costo
- Un solo warehouse serverless pequeño, que se apaga cuando no se usa.
- El dato es pequeño (decenas de filas): no se usan clusters ni jobs de Spark.

## Limitaciones aceptadas

- **Un solo ambiente:** los Pull Requests y la carga programada escriben en el mismo schema `workspace.demo`. Para un taller es aceptable; en un proyecto real habría un schema o workspace por ambiente (dev / prod).
- **Permisos por grupo** documentados pero no probados con varios usuarios (Free Edition).
- **Alertas** solo por las notificaciones de GitHub. Slack o Teams quedan fuera de alcance.
