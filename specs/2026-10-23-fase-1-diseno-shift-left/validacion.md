# Fase 1 · Diseño y calidad shift-left · Validación

> Criterios de aceptación de la Fase 1. La fase está **lista** cuando todas las casillas están marcadas. Si un criterio no se cumple, se corrige la spec o el código, pero no se deja pasar.
>
> Las consultas SQL se ejecutan en el **SQL Editor** de Databricks, con el warehouse en Running.

## Qué bloquea el merge y qué solo advierte

| Resultado | Efecto |
|---|---|
| Falla un test de `pytest` | ❌ **Bloquea**: el stage 1 queda en rojo y el stage 2 no corre |
| Falla un chequeo estructural del CSV (columna faltante, encabezado distinto, archivo vacío, fila incompleta, no UTF-8) | ❌ **Bloquea**: stage 1 en rojo |
| Falla un script SQL de `sql/ddl/` o la carga de `ref_paises` | ❌ **Bloquea**: stage 2 en rojo |
| Después del despliegue falta una tabla o columna del contrato, o un tipo no coincide | ❌ **Bloquea**: stage 2 en rojo |
| Faltan los secrets o están mal | ❌ **Bloquea**: stage 2 en rojo, con un mensaje que no muestra valores |
| Hay filas con errores de calidad en el CSV | ⚠️ **Advertencia**: stage 1 en verde con `::warning::` y el detalle en el resumen |
| Hay columnas extra en una tabla, fuera del contrato | ⚠️ **Advertencia**: stage 2 en verde y se reportan en el log |

## Valores esperados con el `customers.csv` actual

| Métrica | Valor esperado |
|---|---|
| Filas de datos | **21** |
| `customer_id` únicos | **20** |
| Filas con al menos un error | **9** |
| % filas con error | **42,86 %** |
| Menores de edad (información) | **2** (C004, C009) |

| Motivo | Cantidad | Filas (n.º · customer_id) |
|---|---|---|
| `nombre_vacio` | 2 | 3 · C003, 8 · C008 |
| `email_invalido` | 2 | 5 · C005, 12 · C011 |
| `email_vacio` | 1 | 20 · C019 |
| `edad_vacia` | 1 | 13 · C012 |
| `edad_no_numerica` | 1 | 16 · C015 |
| `pais_vacio` | 1 | 17 · C016 |
| `duplicado` | 1 | 11 · C010 |
| `customer_id_vacio`, `edad_fuera_de_rango`, `pais_desconocido` | 0 | — |

La numeración de filas empieza en 1 con la primera fila de datos, sin contar el encabezado.

---

## Criterios de aceptación

### A · Calidad shift-left (stage 1)

- [ ] **A1. El stage shift-left corre primero en el Pull Request.**
  - **Cómo:** en la pestaña *Checks* del PR o en *Actions*, mirar el grafo del workflow.
  - **Stage:** 1 · Calidad shift-left.
  - **Esperado:** `Calidad shift-left` empieza primero y `Despliegue del modelo` solo empieza cuando el primero termina en verde.
  - **Si falla:** bloquea.

- [ ] **A2. Los tests automáticos pasan.**
  - **Cómo:** log del paso `pytest` en el job (o `pytest` en local).
  - **Stage:** 1.
  - **Esperado:** 0 tests fallidos. Hay al menos un test por cada regla de calidad, uno por cada fixture estructural y uno con los números del CSV real.
  - **Si falla:** bloquea.

- [ ] **A3. Los chequeos estructurales detectan un archivo roto.**
  - **Cómo:** los tests con `tests/fixtures/falta_columna.csv`, `encabezado_desordenado.csv`, `solo_encabezado.csv`, `vacio.csv` y `fila_incompleta.csv`.
  - **Stage:** 1.
  - **Esperado:** con cada fixture, `validar_csv.py` termina con código `1` y un mensaje que dice qué falló.
  - **Si falla:** bloquea.

- [ ] **A4. El reporte del CSV real da los números esperados.**
  - **Cómo:** abrir el **resumen** (*Summary*) del job `Calidad shift-left`.
  - **Stage:** 1.
  - **Esperado:** los valores de las tablas de [valores esperados](#valores-esperados-con-el-customerscsv-actual): 21 filas, 20 únicos, 9 con error (42,86 %), 2 menores y el conteo exacto por motivo.
  - **Si falla:** bloquea, porque el test con el CSV real falla.

- [ ] **A5. Los errores por fila solo advierten.**
  - **Cómo:** mirar el estado del job y las anotaciones del PR.
  - **Stage:** 1.
  - **Esperado:** el job termina **en verde** y muestra una advertencia (`::warning::`) de 9 filas con error.
  - **Si falla:** advertencia (es el comportamiento esperado).

- [ ] **A6. El reporte no muestra emails.**
  - **Cómo:** buscar `@` en el log y en el resumen del job `Calidad shift-left`. También lo comprueba un test automático.
  - **Stage:** 1.
  - **Esperado:** 0 apariciones de `@`.
  - **Si falla:** bloquea.

- [ ] **A7. El stage shift-left no usa secrets ni toca Databricks.**
  - **Cómo:** revisar `.github/workflows/pipeline.yml`.
  - **Stage:** 1.
  - **Esperado:** el job `Calidad shift-left` no tiene ninguna referencia a `secrets.`.
  - **Si falla:** bloquea, en la revisión del PR.

### B · Despliegue del modelo (stage 2)

- [ ] **B1. Las 6 tablas existen en `workspace.demo`.**
  - **Cómo:**
    ```sql
    SHOW TABLES IN workspace.demo;
    ```
  - **Stage:** 2 · Despliegue del modelo.
  - **Esperado:** aparecen `bronze_customers`, `silver_customers`, `rechazados_customers`, `ref_paises`, `gold_contactables_pais` y `monitoreo_ejecuciones`.
  - **Si falla:** bloquea.

- [ ] **B2. Columnas y tipos coinciden con el contrato.**
  - **Cómo:** lo verifica el script de despliegue contra `sql/contrato_modelo.json`. Para revisarlo a mano:
    ```sql
    SELECT table_name, column_name, data_type, is_nullable
    FROM workspace.information_schema.columns
    WHERE table_schema = 'demo'
    ORDER BY table_name, ordinal_position;
    ```
  - **Stage:** 2.
  - **Esperado:** cada tabla tiene exactamente las columnas y tipos de [requerimientos.md](requerimientos.md#datos-de-salida). El log del stage dice que el contrato se verificó sin diferencias.
  - **Si falla:** bloquea.

- [ ] **B3. El contrato y los DDL no se contradicen.**
  - **Cómo:** test automático que compara `sql/contrato_modelo.json` con las columnas de `sql/ddl/*.sql`.
  - **Stage:** 1.
  - **Esperado:** el test pasa.
  - **Si falla:** bloquea.

- [ ] **B4. `ref_paises` tiene los 5 países con nombre y región.**
  - **Cómo:**
    ```sql
    SELECT * FROM workspace.demo.ref_paises ORDER BY country_code;
    ```
  - **Stage:** 2.
  - **Esperado:** 5 filas:

    | country_code | country_name | region |
    |---|---|---|
    | AR | Argentina | Sudamérica |
    | CL | Chile | Sudamérica |
    | CO | Colombia | Sudamérica |
    | MX | México | Norteamérica |
    | PE | Perú | Sudamérica |
  - **Si falla:** bloquea.

- [ ] **B5. Las demás tablas quedan creadas y vacías.**
  - **Cómo:**
    ```sql
    SELECT 'bronze_customers' AS tabla, COUNT(*) AS filas FROM workspace.demo.bronze_customers
    UNION ALL SELECT 'silver_customers', COUNT(*) FROM workspace.demo.silver_customers
    UNION ALL SELECT 'rechazados_customers', COUNT(*) FROM workspace.demo.rechazados_customers
    UNION ALL SELECT 'gold_contactables_pais', COUNT(*) FROM workspace.demo.gold_contactables_pais
    UNION ALL SELECT 'monitoreo_ejecuciones', COUNT(*) FROM workspace.demo.monitoreo_ejecuciones;
    ```
  - **Stage:** 2.
  - **Esperado:** 0 filas en cada una.
  - **Si falla:** advertencia (no rompe nada, pero indica que algo cargó datos fuera de la spec).

- [ ] **B6. Gold no tiene emails y la PII está marcada.**
  - **Cómo:**
    ```sql
    SELECT table_name, column_name, comment
    FROM workspace.information_schema.columns
    WHERE table_schema = 'demo'
      AND (lower(column_name) LIKE '%email%' OR column_name = 'registro_original');
    ```
  - **Stage:** 2.
  - **Esperado:** aparecen solo `bronze_customers.email`, `silver_customers.email` y `rechazados_customers.registro_original`, y cada comentario incluye `PII`. **Ninguna fila** de `gold_contactables_pais`.
  - **Si falla:** bloquea.

- [ ] **B7. Las tablas se crearon desde el pipeline y no a mano.**
  - **Cómo:**
    ```sql
    DESCRIBE HISTORY workspace.demo.ref_paises;
    ```
    Comparar con el log del job `Despliegue del modelo`.
  - **Stage:** 2.
  - **Esperado:** la operación `CREATE TABLE` y los `MERGE` coinciden en fecha y hora con las ejecuciones del workflow. No hay scripts SQL fuera de `sql/ddl/`.
  - **Si falla:** bloquea, en la revisión del PR.

### C · Idempotencia

- [ ] **C1. Correr el despliegue dos veces no falla ni duplica.**
  - **Cómo:** en el PR, *Re-run all jobs* y luego repetir B1, B2 y B4.
  - **Stage:** 2.
  - **Esperado:** la segunda ejecución termina en verde, siguen las 6 tablas y `ref_paises` sigue con **5** filas.
  - **Si falla:** bloquea.

### D · Seguridad y gobierno

- [ ] **D1. No hay credenciales en el repo.**
  - **Cómo:** buscar `dapi` y `DATABRICKS_TOKEN=` en el repo, y revisar que **Secret scanning** y **Push protection** estén activos en *Settings → Advanced Security*.
  - **Stage:** revisión del PR.
  - **Esperado:** 0 resultados en la búsqueda, y ambas protecciones activas.
  - **Si falla:** bloquea.

- [ ] **D2. Los secrets solo llegan al stage 2.**
  - **Cómo:** revisar `.github/workflows/pipeline.yml`.
  - **Stage:** revisión del PR.
  - **Esperado:** `secrets.DATABRICKS_*` aparece solo en el job `Despliegue del modelo`, y el workflow declara `permissions: contents: read`.
  - **Si falla:** bloquea.

- [ ] **D3. Si faltan secrets, el error no los muestra.**
  - **Cómo:** test automático de `scripts/db.py` sin variables de entorno.
  - **Stage:** 1.
  - **Esperado:** falla con un mensaje que nombra la variable faltante, sin mostrar ningún valor.
  - **Si falla:** bloquea.

- [ ] **D4. El script de permisos existe y no se ejecuta.**
  - **Cómo:** revisar `sql/permisos.sql` y el workflow.
  - **Stage:** revisión del PR.
  - **Esperado:** el archivo implementa la matriz de acceso de la constitución, y el workflow no lo ejecuta.
  - **Si falla:** advertencia.

### E · Pipeline, ramas y documentación

- [ ] **E1. Dos ejecuciones no corren a la vez.**
  - **Cómo:** revisar `concurrency` en `.github/workflows/pipeline.yml`.
  - **Stage:** revisión del PR.
  - **Esperado:** grupo `databricks-workspace-demo` con `cancel-in-progress: false`.
  - **Si falla:** advertencia.

- [ ] **E2. Los dos stages son checks obligatorios de `main`.**
  - **Cómo:** *Settings → Rules → proteger-main → Require status checks to pass*.
  - **Stage:** configuración de GitHub (después de la primera ejecución).
  - **Esperado:** aparecen **`Calidad shift-left`** y **`Despliegue del modelo`** como requeridos, y el PR muestra "Required" en ambos.
  - **Si falla:** bloquea el cierre de la fase.

- [ ] **E3. El README documenta cada script.**
  - **Cómo:** leer la sección "Scripts del pipeline" del `README.md`.
  - **Stage:** revisión del PR.
  - **Esperado:** cada archivo de `scripts/` y `sql/` aparece con qué hace y en qué stage corre, y hay instrucciones para correr las pruebas en local.
  - **Si falla:** bloquea el cierre de la fase.

- [ ] **E4. El PR se mergea solo en verde.**
  - **Cómo:** estado del PR en GitHub.
  - **Stage:** merge.
  - **Esperado:** ambos stages en verde antes del merge a `main`. Nadie hizo push directo a `main`.
  - **Si falla:** bloquea.
