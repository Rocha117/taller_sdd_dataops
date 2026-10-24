# Fase 2 · Pipeline de punta a punta · Validación

> Criterios de aceptación de la Fase 2. La fase está **lista** cuando todas las casillas están marcadas, salvo la de la sección H, que se comprueba después del merge. Si un criterio no se cumple, se corrige la spec o el código, pero no se deja pasar.
>
> Las consultas SQL se ejecutan en el **SQL Editor** de Databricks. Las que miran "la última carga" toman el `run_id` de Silver, que siempre tiene solo la última carga buena.

## Qué bloquea el merge y qué solo advierte

| Resultado | Stage | Efecto |
|---|---|---|
| Falla un test de `pytest` | 1 | ❌ **Bloquea** |
| Falla un chequeo estructural del CSV | 1 | ❌ **Bloquea** |
| `% filas con error >= 50` en el CSV | 1 | ❌ **Bloquea**, antes de tocar Databricks |
| Falla un script SQL o el contrato del modelo | 2 | ❌ **Bloquea** |
| Las filas de Bronze de la ejecución no coinciden con las del archivo | 3 | ❌ **Bloquea** |
| `% rechazos >= 50` en el stage de calidad | 4 | ❌ **Bloquea**: Silver no se toca y Gold no corre |
| `SUM(clientes_unicos)` o `SUM(clientes_contactables)` de Gold no cuadran | 5 | ❌ **Bloquea** |
| Algún stage del 1 al 5 no terminó en verde, o no quedaron 6 filas de monitoreo | 6 | ❌ **Bloquea** |
| Hay filas con error, pero menos del 50 % | 1 y 4 | ⚠️ **Advertencia**: verde con `::warning::` |
| Columnas extra fuera del contrato | 2 | ⚠️ **Advertencia** |

## Valores esperados por ejecución, con el `customers.csv` actual

| Tabla / métrica | Valor esperado |
|---|---|
| Bronze, filas con el `run_id` de la ejecución | **21** |
| Silver | **12** filas: C001, C002, C004, C006, C007, C009, C010, C013, C014, C017, C018, C020 |
| Silver contactables (`es_contactable = true`) | **10** (todas menos C004 y C009) |
| Silver menores (`es_mayor_edad = false`) | **2**: C004, C009 |
| Rechazados de la ejecución | **9** (42,86 %) |
| Gold | **6** filas |
| KPI global | **50,00 %** (10 / 20), meta 80 % |
| Monitoreo de la ejecución | **6** filas |

**Rechazados esperados**

| `_row_number` | `customer_id` | `motivo` |
|---|---|---|
| 3 | C003 | `nombre_vacio` |
| 5 | C005 | `email_invalido` |
| 8 | C008 | `nombre_vacio` |
| 11 | C010 | `duplicado` |
| 12 | C011 | `email_invalido` |
| 13 | C012 | `edad_vacia` |
| 16 | C015 | `edad_no_numerica` |
| 17 | C016 | `pais_vacio` |
| 20 | C019 | `email_vacio` |

**Gold esperado**

| `country_code` | `country_name` | `region` | `clientes_unicos` | `clientes_contactables` | `pct_contactables` |
|---|---|---|---|---|---|
| AR | Argentina | Sudamérica | 2 | 1 | 50.00 |
| CL | Chile | Sudamérica | 3 | 1 | 33.33 |
| CO | Colombia | Sudamérica | 2 | 1 | 50.00 |
| MX | México | Norteamérica | 2 | 1 | 50.00 |
| PE | Perú | Sudamérica | 10 | 6 | 60.00 |
| ZZ | Sin país | Sin región | 1 | 0 | 0.00 |

**Monitoreo esperado** (por ejecución)

| `stage` | `estado` | `filas_entrada` | `filas_salida` | `filas_rechazadas` |
|---|---|---|---|---|
| `shift_left` | `advertencia` | 21 | 12 | 9 |
| `despliegue_modelo` | `exito` | NULL | 5 | NULL |
| `bronze` | `exito` | 21 | 21 | NULL |
| `calidad` | `advertencia` | 21 | 12 | 9 |
| `gold` | `exito` | 12 | 6 | NULL |
| `monitoreo` | `exito` | 5 | 6 | 0 |

---

## Criterios de aceptación

### A · Stage 1 · Shift-left ampliado

- [x] **A1. Bloquea con 50 % o más de filas con error.**
  - **Cómo:** tests con `tests/fixtures/mayoria_con_error.csv` y con el límite exacto de 50 %.
  - **Stage:** 1.
  - **Esperado:** código de salida `1` y `::error::` que menciona el umbral.
  - **Si falla:** bloquea.

- [x] **A2. Con el CSV actual sigue en verde, con advertencia.**
  - **Cómo:** resumen del job `Calidad shift-left`.
  - **Stage:** 1.
  - **Esperado:** verde, `::warning::` de 9 de 21 filas (42,86 %), y el texto indica el umbral de 50 %.
  - **Si falla:** bloquea.

- [x] **A3. Sigue sin secrets ni Databricks.**
  - **Cómo:** revisar `.github/workflows/pipeline.yml`.
  - **Stage:** revisión del PR.
  - **Esperado:** el job `Calidad shift-left` no referencia `secrets.`.
  - **Si falla:** bloquea.

### B · Stage 3 · Ingesta a Bronze

- [x] **B1. Bronze tiene 21 filas de la última ejecución, en orden.**
  - **Cómo:**
    ```sql
    WITH ultima AS (SELECT DISTINCT _run_id FROM workspace.demo.silver_customers)
    SELECT COUNT(*) AS filas, MIN(_row_number) AS primera, MAX(_row_number) AS ultima_fila,
           MIN(_source_file) AS archivo
    FROM workspace.demo.bronze_customers
    WHERE _run_id IN (SELECT _run_id FROM ultima);
    ```
  - **Stage:** 3.
  - **Esperado:** `filas = 21`, `primera = 1`, `ultima_fila = 21` y `archivo = data/source/customers.csv`.
  - **Si falla:** bloquea.

- [x] **B2. Bronze guarda el dato crudo.**
  - **Cómo:**
    ```sql
    WITH ultima AS (SELECT DISTINCT _run_id FROM workspace.demo.silver_customers)
    SELECT customer_id, length(name) AS largo_nombre, age
    FROM workspace.demo.bronze_customers
    WHERE _run_id IN (SELECT _run_id FROM ultima) AND customer_id IN ('C008', 'C015');
    ```
  - **Stage:** 3.
  - **Esperado:** C008 con `largo_nombre = 2` (los dos espacios se conservan) y C015 con `age = abc`.
  - **Si falla:** bloquea.

### C · Stage 4 · Calidad de datos

- [x] **C1. Silver tiene las 12 filas válidas, normalizadas y con banderas.**
  - **Cómo:**
    ```sql
    SELECT customer_id, age, country_code, es_mayor_edad, es_contactable
    FROM workspace.demo.silver_customers ORDER BY customer_id;
    ```
  - **Stage:** 4.
  - **Esperado:** las 12 filas de la tabla de [valores esperados](#valores-esperados-por-ejecución-con-el-customerscsv-actual), un solo `_run_id`, `es_mayor_edad = false` y `es_contactable = false` solo en C004 y C009, y `true` en las otras 10.
  - **Si falla:** bloquea.

- [x] **C2. Ningún registro con error llegó a Silver.**
  - **Cómo:**
    ```sql
    SELECT COUNT(*) AS con_error FROM workspace.demo.silver_customers
    WHERE trim(name) = '' OR email NOT RLIKE '^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$'
       OR country_code NOT IN (SELECT country_code FROM workspace.demo.ref_paises)
       OR age < 0 OR age > 120;
    ```
    También:
    ```sql
    SELECT customer_id, COUNT(*) FROM workspace.demo.silver_customers
    GROUP BY customer_id HAVING COUNT(*) > 1;
    ```
  - **Stage:** 4.
  - **Esperado:** `con_error = 0` y la segunda consulta sin filas.
  - **Si falla:** bloquea.

- [x] **C3. Los 9 rechazados tienen su motivo y su registro original.**
  - **Cómo:**
    ```sql
    WITH ultima AS (SELECT DISTINCT _run_id FROM workspace.demo.silver_customers)
    SELECT _row_number, customer_id, motivo, registro_original
    FROM workspace.demo.rechazados_customers
    WHERE _run_id IN (SELECT _run_id FROM ultima)
    ORDER BY _row_number;
    ```
  - **Stage:** 4.
  - **Esperado:** las 9 filas de [rechazados esperados](#valores-esperados-por-ejecución-con-el-customerscsv-actual). `registro_original` es un JSON con los 5 campos crudos (por ejemplo, C008 con `"name": "  "`), con acentos legibles.
  - **Si falla:** bloquea.

- [x] **C4. Con 50 % o más, se guardan los rechazados y no se toca Silver.**
  - **Cómo:** tests de `tests/test_calidad_datos.py` con un cursor falso.
  - **Stage:** 1 (tests).
  - **Esperado:** con ≥ 50 % se ejecutan el `DELETE` y el `INSERT` de rechazados, **no** se ejecuta el `INSERT OVERWRITE` de Silver, el estado es `fallo` y el código de salida es `1`.
  - **Si falla:** bloquea.

- [x] **C5. Advierte con rechazos por debajo del umbral.**
  - **Cómo:** resumen y anotaciones del job `Calidad de datos`.
  - **Stage:** 4.
  - **Esperado:** verde, con `::warning::` de 9 de 21 filas rechazadas (42,86 %).
  - **Si falla:** advertencia (es el comportamiento esperado).

### D · Stage 5 · Gold

- [x] **D1. Gold tiene el indicador por país esperado.**
  - **Cómo:**
    ```sql
    SELECT country_code, country_name, region, clientes_unicos, clientes_contactables, pct_contactables
    FROM workspace.demo.gold_contactables_pais ORDER BY country_code;
    ```
  - **Stage:** 5.
  - **Esperado:** exactamente las 6 filas de [Gold esperado](#valores-esperados-por-ejecución-con-el-customerscsv-actual).
  - **Si falla:** bloquea.

- [x] **D2. Gold cuadra con el KPI global.**
  - **Cómo:**
    ```sql
    SELECT SUM(clientes_unicos) AS unicos, SUM(clientes_contactables) AS contactables,
           ROUND(100 * SUM(clientes_contactables) / SUM(clientes_unicos), 2) AS kpi_pct
    FROM workspace.demo.gold_contactables_pais;
    ```
    Comparar con el log del job `Gold`.
  - **Stage:** 5.
  - **Esperado:** `unicos = 20`, `contactables = 10` y `kpi_pct = 50.00`. El log dice "KPI 50,00 % · meta 80 % · faltan 30,00 puntos".
  - **Si falla:** bloquea.

- [x] **D3. Gold no tiene datos personales.**
  - **Cómo:**
    ```sql
    SELECT column_name FROM workspace.information_schema.columns
    WHERE table_schema = 'demo' AND table_name = 'gold_contactables_pais';
    ```
  - **Stage:** 5.
  - **Esperado:** las 8 columnas del contrato. Ninguna tiene email ni nombres de clientes.
  - **Si falla:** bloquea.

### E · Stage 6 · Monitoreo

- [x] **E1. Cada ejecución deja 6 filas con el estado de cada stage.**
  - **Cómo:**
    ```sql
    WITH ultima AS (SELECT DISTINCT _run_id FROM workspace.demo.silver_customers)
    SELECT stage, estado, filas_entrada, filas_salida, filas_rechazadas, `trigger`, git_sha,
           from_utc_timestamp(started_at, 'America/Lima') AS inicio_lima, mensaje
    FROM workspace.demo.monitoreo_ejecuciones
    WHERE run_id IN (SELECT _run_id FROM ultima)
    ORDER BY started_at;
    ```
  - **Stage:** 6.
  - **Esperado:** las 6 filas de [monitoreo esperado](#valores-esperados-por-ejecución-con-el-customerscsv-actual), con `trigger = pull_request` y el `git_sha` del commit del PR. Ningún `mensaje` contiene `@`.
  - **Si falla:** bloquea.

- [x] **E2. El monitoreo registra los fallos.**
  - **Cómo:** tests de `tests/test_monitoreo.py`.
  - **Stage:** 1 (tests).
  - **Esperado:** si el stage 1 falla, se arman 6 filas: `shift_left` = `fallo`, del 2 al 5 = `fallo` con "No corrió: falló un stage anterior", y el monitoreo termina con código `1`.
  - **Si falla:** bloquea.

- [x] **E3. El monitoreo corre siempre.**
  - **Cómo:** revisar el job `Monitoreo` en `.github/workflows/pipeline.yml`.
  - **Stage:** revisión del PR.
  - **Esperado:** `needs` de los 5 jobs e `if: always()`.
  - **Si falla:** bloquea.

### F · Idempotencia, disparadores y mejoras

- [x] **F1. Una ejecución nueva no duplica Silver ni Gold.**
  - **Cómo:** *Re-run all jobs* en el PR y repetir C1, D1 y E1. Además:
    ```sql
    SELECT _run_id, COUNT(*) FROM workspace.demo.bronze_customers GROUP BY _run_id ORDER BY _run_id;
    ```
  - **Stage:** 3 a 6.
  - **Esperado:** Silver sigue con 12 filas y Gold con 6, ahora con el `run_id` nuevo. Bronze tiene 21 filas **por cada** `run_id` (es historia, no duplicación). El monitoreo tiene 6 filas por `run_id`.
  - **Si falla:** bloquea.

- [ ] **F2. El `MERGE` de países no reescribe si no hay cambios.**
  - **Cómo:**
    ```sql
    DESCRIBE HISTORY workspace.demo.ref_paises LIMIT 5;
    ```
  - **Stage:** 2.
  - **Esperado:** en las ejecuciones de la Fase 2, los `MERGE` tienen `numTargetRowsUpdated = 0` y `numTargetRowsInserted = 0`, o no hay versión nueva.
  - **Si falla:** advertencia.

- [x] **F3. La ejecución manual funciona y queda registrada.**
  - **Cómo:** *Actions → Pipeline ClientesConfiables → Run workflow* sobre la rama, y luego E1 con esa ejecución.
  - **Stage:** 1 a 6.
  - **Esperado:** los 6 stages en verde y `trigger = manual` en las 6 filas de monitoreo.
  - **Si falla:** bloquea.

- [x] **F4. La carga de los lunes está programada.**
  - **Cómo:** revisar `.github/workflows/pipeline.yml`.
  - **Stage:** revisión del PR.
  - **Esperado:** `schedule` con `cron: "0 11 * * 1"`.
  - **Si falla:** bloquea.

- [x] **F5. Ya no aparece el aviso de Node 20.**
  - **Cómo:** anotaciones del workflow en el PR.
  - **Stage:** todos.
  - **Esperado:** el workflow usa `actions/checkout@v5` y `actions/setup-python@v6`, y no hay avisos de Node 20.
  - **Si falla:** advertencia.

### G · Seguridad, pipeline y documentación

- [x] **G1. Ningún log muestra emails.**
  - **Cómo:** buscar `@` en los logs y resúmenes de los 6 jobs. También lo comprueban tests automáticos.
  - **Stage:** todos.
  - **Esperado:** 0 apariciones.
  - **Si falla:** bloquea.

- [x] **G2. Los secrets solo llegan a los stages 2 a 6.**
  - **Cómo:** revisar `.github/workflows/pipeline.yml`.
  - **Stage:** revisión del PR.
  - **Esperado:** `secrets.DATABRICKS_*` aparece solo en los pasos que ejecutan los scripts de los stages 2 a 6, y el workflow declara `permissions: contents: read`.
  - **Si falla:** bloquea.

- [x] **G3. Los 6 stages son checks obligatorios de `main`.**
  - **Cómo:** *Settings → Rules → proteger-main*.
  - **Stage:** configuración de GitHub.
  - **Esperado:** `Calidad shift-left`, `Despliegue del modelo`, `Ingesta a Bronze`, `Calidad de datos`, `Gold` y `Monitoreo` aparecen como requeridos.
  - **Si falla:** bloquea el cierre de la fase.

- [x] **G4. El repo está listo para ejecutar con solo 3 secrets.**
  - **Cómo:** leer el apartado "Listo para ejecutar" y "Scripts del pipeline" del `README.md`.
  - **Stage:** revisión del PR.
  - **Esperado:** cada script aparece con su stage, y están los pasos de fork, schema `demo` y 3 secrets, el schedule y cómo reactivarlo, la diferencia entre los tipos de re-run y las fechas en UTC.
  - **Si falla:** bloquea el cierre de la fase.

- [x] **G5. El PR se mergea solo en verde.**
  - **Cómo:** estado del PR en GitHub.
  - **Stage:** merge.
  - **Esperado:** los 6 stages en verde antes del merge a `main`.
  - **Si falla:** bloquea.

## Después del merge (no bloquea el merge)

- [ ] **H1. La primera carga programada llega antes de las 8:00.** El primer lunes después del merge, consultar `monitoreo_ejecuciones` con `` `trigger` = 'schedule' ``. Esperado: 6 filas con `inicio_lima` antes de las 8:00 y los 6 stages en `exito` o `advertencia`.

---

## Resultado de la validación

**Fase 2 cumplida el 2026-10-23.** Quedan dos casillas sin marcar, ninguna bloquea el merge:
- **F2** (opcional, solo advertencia): `DESCRIBE HISTORY ref_paises` no se revisó.
- **H1** (después del merge): se comprueba el primer lunes.

| Evidencia | Dónde |
|---|---|
| Los 6 stages en verde en el PR (`run_id` `40055185878-1`), en el re-run (`40055185878-2`) y en la ejecución manual (`40058328679-1`) | [PR #3](https://github.com/Rocha117/taller_sdd_dataops/pull/3) · GitHub Actions |
| A: shift-left con advertencia de 9 de 21 filas (42,86 %). Los tests de umbral (A1) y de fallos (C4, E2) pasan: 145 tests | Job `Calidad shift-left` |
| B1, B2: Bronze con 21 filas (de la 1 a la 21, `data/source/customers.csv`), C008 con nombre de 2 espacios y C015 con `abc` | SQL Editor de Databricks |
| C1 a C3: Silver con 12 filas (C004 y C009 menores, no contactables), `con_error = 0`, y 9 rechazados con motivo y JSON crudo | SQL Editor de Databricks |
| D1, D2: Gold con 6 filas (PE 60 %, CL 33,33 %, CO, MX y AR 50 %, ZZ 0 %). KPI 20 / 10 / 50 % | SQL Editor de Databricks · job `Gold` |
| E1: 6 filas de monitoreo con el estado esperado y `trigger = pull_request` | SQL Editor de Databricks |
| F1: el re-run deja Silver con 12 y Gold con 6, con el nuevo `run_id` | SQL Editor de Databricks |
| F3: ejecución manual con 6 filas de monitoreo y `trigger = manual` | Resumen del job `Monitoreo` |
| F5: sin avisos de Node 20 (`checkout@v5`, `setup-python@v6`) | Anotaciones del workflow |
| G1: 0 emails de clientes en los logs de las 3 ejecuciones | Búsqueda en los logs de GitHub Actions |
| G3: los 6 stages son checks obligatorios en `proteger-main` | Ruleset de `main` |
| G5: merge a `main` solo con los 6 checks en verde (lo exige el ruleset) | PR #3 |
