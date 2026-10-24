# Fase 1 · Diseño y calidad shift-left · Plan

> Tareas en el orden en que se construyen. Cada tarea indica el archivo que crea o modifica. Respeta [requerimientos.md](requerimientos.md) y el [stack tecnológico](../../constitucion/stack-tecnologico.md). Se trabaja solo en la rama `feat/fase-1-diseno-shift-left`.

## Grupo 1 · Base del repo

- [ ] **1.1** Crear `requirements.txt` con versiones fijadas de `databricks-sql-connector` y `pytest`.
- [ ] **1.2** Revisar `.gitignore`: debe seguir ignorando `.env`, `.venv/` y `__pycache__/`. Agregar `.pytest_cache/`.
- [ ] **1.3** Crear `data/reference/paises.csv` con los 5 países, su nombre y su región.

## Grupo 2 · Reglas de calidad y validador shift-left

- [ ] **2.1** Crear `scripts/reglas_calidad.py`:
  - normalización (quitar espacios, país en mayúsculas);
  - una función por regla por fila, que devuelve su motivo o nada;
  - una función que evalúa todas las filas en orden y devuelve, por fila, sus motivos (incluido `duplicado`) y si es menor de edad.

  Sin dependencias de Databricks.
- [ ] **2.2** Crear `scripts/validar_csv.py`:
  - chequeos estructurales (existe, UTF-8, encabezado exacto, al menos una fila, 5 campos por fila);
  - evaluación por fila usando `reglas_calidad.py` y `data/reference/paises.csv`;
  - reporte en `GITHUB_STEP_SUMMARY` (o en consola si no existe esa variable);
  - `::warning::` si hay filas con error;
  - código de salida `1` solo si falla un chequeo estructural;
  - nunca imprime emails.
- [ ] **2.3** Crear los CSV de prueba en `tests/fixtures/`:
  - `falta_columna.csv`
  - `encabezado_desordenado.csv`
  - `solo_encabezado.csv`
  - `vacio.csv`
  - `fila_incompleta.csv`
  - `valido_minimo.csv` (una fila sin errores)
- [ ] **2.4** Crear `tests/test_reglas_calidad.py`. Incluye un caso por cada regla y motivo, varios motivos en una fila, el duplicado (manda la primera fila), un menor de edad válido sin motivo, y la normalización (espacios y mayúsculas).
- [ ] **2.5** Crear `tests/test_validar_csv.py`:
  - cada fixture estructural debe fallar con su mensaje;
  - `valido_minimo.csv` pasa sin advertencias;
  - el `customers.csv` real da los números exactos de [validacion.md](validacion.md);
  - el reporte nunca contiene un `@`.
- [ ] **2.6** Correr `pytest` en local y dejar todo en verde.

## Grupo 3 · Modelo de datos

- [ ] **3.1** Crear `sql/ddl/01_bronze_customers.sql`.
- [ ] **3.2** Crear `sql/ddl/02_silver_customers.sql`.
- [ ] **3.3** Crear `sql/ddl/03_rechazados_customers.sql`.
- [ ] **3.4** Crear `sql/ddl/04_ref_paises.sql`.
- [ ] **3.5** Crear `sql/ddl/05_gold_contactables_pais.sql`.
- [ ] **3.6** Crear `sql/ddl/06_monitoreo_ejecuciones.sql`.
- [ ] **3.7** Crear `sql/contrato_modelo.json` con las 6 tablas, sus columnas y tipos, igual que en los DDL.
- [ ] **3.8** Crear `sql/permisos.sql` con los `GRANT` de la matriz de acceso (no lo ejecuta el pipeline).

Todos los DDL siguen los de [requerimientos.md](requerimientos.md#datos-de-salida) al pie de la letra: `CREATE TABLE IF NOT EXISTS`, `{{catalog}}.{{schema}}`, comentarios en tabla y columnas, y sin `DROP`.

## Grupo 4 · Despliegue del modelo

- [ ] **4.1** Crear `scripts/db.py`. Abre la conexión con `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH` y `DATABRICKS_TOKEN` desde variables de entorno. Si falta alguna, falla con un mensaje claro **sin mostrar valores**. También reemplaza `{{catalog}}` y `{{schema}}` (por defecto `workspace` y `demo`).
- [ ] **4.2** Crear `scripts/desplegar_modelo.py`:
  1. imprime el `run_id`;
  2. ejecuta los archivos de `sql/ddl/` en orden numérico;
  3. carga `ref_paises` con el `MERGE` parametrizado;
  4. verifica el modelo contra `sql/contrato_modelo.json` en `information_schema.columns`;
  5. imprime un resumen de tablas y filas de `ref_paises`.

  Si un paso falla, termina con código `1`.
- [ ] **4.3** Crear `tests/test_contrato.py`, que compara `sql/contrato_modelo.json` con las columnas de los DDL. Así un DDL y el contrato no pueden quedar distintos sin que falle el stage 1.
- [ ] **4.4** Crear `tests/test_db.py`: sin las variables de entorno, `scripts/db.py` falla con un mensaje que nombra la variable faltante y no muestra ningún valor. El test no se conecta a Databricks.

## Grupo 5 · Workflow de GitHub Actions

- [ ] **5.1** Crear `.github/workflows/pipeline.yml`:
  - disparadores `pull_request` hacia `main` y `workflow_dispatch`;
  - `permissions: contents: read`;
  - `concurrency` con grupo `databricks-workspace-demo` y `cancel-in-progress: false`.
- [ ] **5.2** Job **`Calidad shift-left`**: checkout, Python 3.11, instalar `requirements.txt`, `pytest`, `python scripts/validar_csv.py`. Sin secrets.
- [ ] **5.3** Job **`Despliegue del modelo`**: `needs` el job anterior, recibe los 3 secrets como variables de entorno y el `run_id` desde `github.run_id` y `github.run_attempt`, y corre `python scripts/desplegar_modelo.py`.

## Grupo 6 · Documentación

- [ ] **6.1** Agregar al `README.md` la sección **"Scripts del pipeline"**: una tabla con cada script y archivo SQL, qué hace y en qué stage corre. Incluir cómo correr `pytest` y `validar_csv.py` en local, y aclarar que `sql/permisos.sql` no lo ejecuta el pipeline.

## Grupo 7 · Configuración de GitHub (la hace la persona, no el asistente)

- [ ] **7.1** Activar **Secret scanning** y **Push protection**: *Settings → Advanced Security* (o *Code security*) del fork.
- [ ] **7.2** Después de la primera ejecución del workflow, agregar **`Calidad shift-left`** y **`Despliegue del modelo`** como *required status checks* en el ruleset `proteger-main`.

## Grupo 8 · Pull Request y validación

- [ ] **8.1** Commit en la rama de la fase (`feat: fase 1 según spec`) y push.
- [ ] **8.2** Abrir el Pull Request hacia `main` del fork, **sin hacer merge**.
- [ ] **8.3** Comprobar en GitHub Actions que los dos stages corren en orden y terminan en verde (el shift-left con su advertencia por filas con error).
- [ ] **8.4** Volver a correr el workflow (*Re-run all jobs*) para comprobar la idempotencia.
- [ ] **8.5** Recorrer [validacion.md](validacion.md) y marcar cada casilla. Si todo cumple, hacer merge a `main`.
