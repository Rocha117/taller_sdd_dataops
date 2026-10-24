# Taller SDD para Datos: del prompt a la spec y de la spec al pipeline

Taller práctico de **Spec-Driven Development (SDD)** aplicado a datos. En vez de pedirle a un asistente de IA "hazme un pipeline", primero escribimos **qué** queremos y **cómo sabremos que está listo**. Esa especificación (spec) es la que guía la construcción.

Vamos a recorrer el **ciclo del dato** completo sobre un archivo de clientes (`customers.csv`):

```
Diseño  →  Build (Bronze → Silver → Gold)  →  Test  →  Deploy  →  Monitoring
```

> **Idea clave:** no te cases con ninguna herramienta. Aquí usamos Databricks y GitHub Actions como ejemplo, pero la spec es la misma si mañana usas otra plataforma. Lo que se queda contigo es el método.

---

## ¿Qué vas a construir?

Al terminar tendrás en este repo:

1. **La constitución** del proyecto (`constitucion/`): la misión, el stack tecnológico y el roadmap. Es la base de conocimiento del proyecto y se consulta en cada feature.
2. **Una feature spec por cada fase** del roadmap: requerimientos, plan y validación.
3. **El modelo de datos** creado en Databricks desde el código: Bronze, Silver, Gold, una tabla de rechazados y una tabla de países.
4. **El pipeline** que tu asistente de IA construye a partir de esas specs, corriendo por stages en GitHub Actions. Nada llega a `main` sin pasar todos los stages.

## El pipeline que vas a especificar

No te lo damos hecho: lo describes en la constitución y tu asistente lo construye. Esta es la forma que pide el negocio:

```
rama de la fase ──► Pull Request ──────────────────────────────────────► merge a main
                     │                                                   (solo si todo
                     ▼                                                    está en verde)
 1. Calidad shift-left   valida el CSV antes de tocar Databricks
 2. Despliegue del modelo crea las tablas desde el código
 3. Ingesta Bronze        guarda el dato crudo
 4. Calidad de datos      válidos → Silver · con error → tabla de rechazados (con motivo)
 5. Gold                  indicador por país (nombre y región), solo mayores de edad
 6. Monitoreo             cada stage deja registro de su ejecución
```

Si un stage falla, el Pull Request queda bloqueado y no se puede hacer merge.

## Las dos partes de SDD

| Parte | Pregunta que responde | Archivo |
|---|---|---|
| **Constitución** · Misión | ¿Por qué existe este dato? ¿Para quién? ¿Qué KPI mueve? | `constitucion/mision.md` |
| **Constitución** · Stack tecnológico | ¿Cómo encaja con la tecnología? Restricciones de equipo, gobierno y calidad | `constitucion/stack-tecnologico.md` |
| **Constitución** · Roadmap | ¿Qué fases están planificadas y en qué orden? | `constitucion/roadmap.md` |
| **Feature Spec** · Scope + Requirements | ¿Qué construye esta fase? ¿Qué restricciones importan? | `specs/AAAA-MM-DD-fase/requerimientos.md` |
| **Feature Spec** · Plan | ¿En qué tareas se divide? | `specs/AAAA-MM-DD-fase/plan.md` |
| **Feature Spec** · Validation | ¿Cómo sabemos que ya está listo? | `specs/AAAA-MM-DD-fase/validacion.md` |

La constitución se escribe **una vez** por proyecto y vive en `constitucion/`, como base de conocimiento. La feature spec se escribe **una vez por cada fase** del roadmap y vive en `specs/`, que solo guarda lo que necesita cada feature.

---

## Requisitos previos

- Una cuenta de **GitHub**.
- Una cuenta de **Databricks Free Edition** con un SQL Warehouse (el mismo del taller de DataOps sirve).
- **Cualquier asistente de IA** que pueda leer y escribir archivos en tu repo, por ejemplo Claude Code, GitHub Copilot, Cursor o Gemini CLI. El taller funciona igual con cualquiera.
- Git instalado en tu computadora (o usa GitHub Codespaces).

## Estructura del repo

```
.
├── README.md                 ← este archivo
├── prompts.md                ← los prompts del taller, en español
├── constitucion/             ← vacío al inicio; base de conocimiento del proyecto
├── negocio/
│   └── input-negocio.md      ← lo que pidieron los stakeholders (entrada de la constitución)
├── data/
│   └── source/
│       └── customers.csv     ← el dato de entrada
└── specs/                    ← vacío al inicio; una carpeta por cada feature
```

No hay código del pipeline al comenzar. **El código sale de la spec**, no al revés.

---

## Paso a paso

### 1. Crea tu copia del repo

Haz **fork** de este repositorio (botón *Fork* arriba a la derecha) y clónalo:

```bash
git clone https://github.com/<tu-usuario>/<nombre-del-repo>.git
cd <nombre-del-repo>
```

✅ Checkpoint: ves `README.md`, `prompts.md`, `constitucion/`, `negocio/`, `data/` y `specs/`.

### 2. Deja listo Databricks

1. En Databricks, ve a **SQL Warehouses** y pulsa **Start** en tu warehouse. Espera a que diga **Running**.
2. Abre el **SQL Editor** y ejecuta:

   ```sql
   CREATE SCHEMA IF NOT EXISTS demo;
   ```

✅ Checkpoint: el warehouse está en Running y el schema `demo` existe.

### 3. Conecta GitHub con Databricks

En tu repo de GitHub: **Settings → Secrets and variables → Actions → New repository secret**. Crea estos 3 secrets:

| Secret | Qué es | Dónde lo encuentras |
|---|---|---|
| `DATABRICKS_HOST` | El host del workspace, sin `https://` (ej. `dbc-xxxx.cloud.databricks.com`) | SQL Warehouses → tu warehouse → Connection details |
| `DATABRICKS_HTTP_PATH` | La ruta del warehouse (ej. `/sql/1.0/warehouses/xxxx`) | SQL Warehouses → tu warehouse → Connection details |
| `DATABRICKS_TOKEN` | Tu token personal | Tu perfil → User settings → Developer → Access tokens → Generate new token |

> 🔒 Nunca pegues el token en un archivo del repo ni en el chat con tu asistente. Solo va en los secrets.

✅ Checkpoint: tienes los 3 secrets creados.

### 3b. Protege la rama `main`

Así nadie (ni tu asistente) puede subir cambios directo a `main`.

1. En tu repo: **Settings → Branches → Add branch ruleset** (o *Add rule*).
2. Aplícalo a la rama `main` y activa:
   - **Require a pull request before merging**, con **Required approvals = 0**. Así el Pull Request no espera que otra persona lo apruebe: lo que lo bloquea o lo deja pasar son los stages del pipeline. (Si trabajas en pareja, puedes subirlo a 1 para que tu compañero/a revise la spec.)
   - **Require status checks to pass**. Los checks del pipeline aparecen aquí después de su primera ejecución; vuelve a este paso para marcarlos.
3. Guarda la regla.

> En cuentas gratuitas de GitHub, la protección de ramas funciona en repos **públicos**. Si tu fork es privado y no la ves, mantenlo público para el taller.

✅ Checkpoint: un `git push` directo a `main` es rechazado.

### 4. Escribe la constitución (Parte 1)

1. Lee [`negocio/input-negocio.md`](negocio/input-negocio.md): es lo que pidieron Marketing, Ingeniería de Datos, Gobierno y BI. Completa en clase la sección "Lo que completamos en clase".
2. Abre tu asistente de IA dentro de la carpeta del repo.
3. Copia el **Prompt 1 · Constitución** de [`prompts.md`](prompts.md) y pégalo. El prompt le pide al asistente leer el input del negocio.
4. El asistente **te hará preguntas antes de escribir**. Respóndelas pensando como el dueño del dato desde el punto de vista de negocio
5. Revisa los tres archivos que crea en `constitucion/`. Si algo no te convence, pídele que lo corrija. **Tú apruebas la spec, no el asistente.**

✅ Checkpoint: existen `constitucion/mision.md`, `constitucion/stack-tecnologico.md` y `constitucion/roadmap.md`, y el roadmap tiene 2 fases que, juntas, cubren todo el ciclo del dato.

Guarda tu avance:

```bash
git add constitucion/
git commit -m "docs: constitución del proyecto"
git push
```

### 5. Escribe la spec de una fase (Parte 2)

1. Copia el **Prompt 2 · Feature Spec** de [`prompts.md`](prompts.md).
2. El asistente toma la **siguiente fase** del roadmap, crea una rama y te pregunta por el detalle.
3. Revisa `requerimientos.md`, `plan.md` y `validacion.md`. Pregúntate: *si alguien más leyera solo esto, ¿construiría lo mismo que yo tengo en la cabeza?*

✅ Checkpoint: existe una carpeta `specs/AAAA-MM-DD-<fase>/` con los tres archivos.

### 6. Construye desde la spec

Pídele al asistente que implemente el `plan.md` de esa fase, **respetando** `requerimientos.md`. El asistente escribirá el código (SQL, Python, workflow de GitHub Actions).

Prompt sugerido (es el **Prompt 3** de [`prompts.md`](prompts.md); cambia la fecha y el nombre de la fase por los tuyos):

```text
Implementa el plan de specs/AAAA-MM-DD-nombre-de-la-fase/plan.md, una tarea a
la vez, respetando requerimientos.md y constitucion/stack-tecnologico.md.

- Después de cada grupo de tareas, dime qué archivos cambiaste.
- Si una tarea no se puede hacer como dice la spec, detente y pregúntame;
  no cambies la spec por tu cuenta.
- Trabaja solo en la rama de esta fase. Cuando termines, prepara el Pull
  Request hacia main, pero no hagas merge: el merge se hace cuando todos los
  stages del pipeline pasan en verde.
- Al final, recorre validacion.md y dime qué criterios puedo comprobar ahora
  y cómo.
```

Sube los cambios y abre un Pull Request:

```bash
git add .
git commit -m "feat: <fase> según spec"
git push -u origin <nombre-de-la-rama>
```

✅ Checkpoint: en el Pull Request ves los stages del pipeline. El primero en correr es el de calidad shift-left, y todos terminan en verde.

### 7. Valida contra la spec

Ejecuta lo que dice `validacion.md` (por ejemplo, las consultas en el SQL Editor de Databricks). Revisa también la tabla de rechazados: cada registro con error tiene que estar ahí, con su motivo. Si todo cumple, haz merge del Pull Request a `main`. Si no, **corrige la spec o el código**, pero no "lo dejes pasar".

✅ Checkpoint: cada criterio de `validacion.md` está marcado como cumplido.

### 8. Repite con la fase 2

Vuelve al paso 5 con la fase 2 del roadmap. Son solo dos fases: la **fase 1** (diseño, modelado y calidad shift-left) y la **fase 2** (pipeline de punta a punta: Bronze, calidad y rechazados, Gold y monitoreo). Cada una tiene su propia rama y su propio Pull Request. Al terminar la fase 2, el pipeline completo corre con solo tus 3 secrets.

---

## El dato: `customers.csv`

Columnas: `customer_id`, `name`, `age`, `country` (código de 2 letras), `email`.

El archivo trae a propósito algunos problemas de calidad (nombres vacíos, países vacíos, edades no numéricas, menores de edad, correos mal formados, duplicados). **No los corrijas a mano**: que tu spec diga qué hacer con ellos.

## Listo para ejecutar

El pipeline completo corre solo con esto:

1. Haz **fork** de este repo y déjalo público (para que funcione la protección de `main`).
2. En Databricks, con el SQL Warehouse en **Running**, ejecuta `CREATE SCHEMA IF NOT EXISTS demo;`.
3. En GitHub, crea los 3 secrets: `DATABRICKS_HOST`, `DATABRICKS_HTTP_PATH` y `DATABRICKS_TOKEN` (ver paso 3).
4. Abre un Pull Request hacia `main`, o ve a *Actions → Pipeline ClientesConfiables → Run workflow*.

Las tablas se crean solas (stage 2) y se llenan de punta a punta (stages 3 a 5). Después, marca los 6 stages como checks obligatorios del ruleset de `main` (paso 3b).

## Scripts del pipeline

Todo lo que corre el workflow [`.github/workflows/pipeline.yml`](.github/workflows/pipeline.yml). Specs: [Fase 1](specs/2026-10-23-fase-1-diseno-shift-left/) y [Fase 2](specs/2026-10-23-fase-2-pipeline-e2e/).

```
1 · Calidad shift-left → 2 · Despliegue del modelo → 3 · Ingesta a Bronze
  → 4 · Calidad de datos → 5 · Gold → 6 · Monitoreo (corre siempre)
```

| Archivo | Qué hace | Stage |
|---|---|---|
| `scripts/validar_csv.py` | Valida `data/source/customers.csv` sin tocar Databricks. **Bloquea** si la estructura está mal o si el 50 % o más de las filas tiene errores; por debajo, solo advierte. Nunca muestra emails | 1 · Calidad shift-left |
| `scripts/reglas_calidad.py` | Las reglas por fila, sus motivos y el umbral de 50 %. Una sola fuente de verdad para los stages 1 y 4 | 1 y 4 |
| `tests/` | Tests de pytest de todos los scripts, con un cursor falso: no se conectan a Databricks | 1 · Calidad shift-left |
| `scripts/desplegar_modelo.py` | Ejecuta `sql/ddl/` en orden, carga `ref_paises` con un `MERGE` que solo actualiza si algo cambió, y verifica el modelo contra `sql/contrato_modelo.json` | 2 · Despliegue del modelo |
| `sql/ddl/01_…06_*.sql` | Crean las 6 tablas (`CREATE TABLE IF NOT EXISTS`), con comentarios y la PII marcada | 2 · Despliegue del modelo |
| `sql/ddl/07_comentario_stage_monitoreo.sql` | Cambio posterior del modelo (solo un comentario). Los cambios futuros van en scripts nuevos numerados | 2 · Despliegue del modelo |
| `sql/contrato_modelo.json` | Tablas, columnas y tipos esperados | 1 (test) y 2 (verificación) |
| `data/reference/paises.csv` | Código, nombre y región de cada país | 1 y 2 |
| `scripts/ingestar_bronze.py` | Carga el CSV **crudo** en `bronze_customers`, con `_run_id`, archivo y número de fila. Falla si el conteo no cuadra | 3 · Ingesta a Bronze |
| `scripts/calidad_datos.py` | Aplica las reglas: los válidos van a `silver_customers` (normalizados, con `es_mayor_edad` y `es_contactable`) y los errores a `rechazados_customers`, con el registro original y el motivo. Con 50 % o más falla y no toca Silver | 4 · Calidad de datos |
| `sql/transformaciones/gold_contactables_pais.sql` | Indicador de contactables por país, con nombre y región. `ZZ` · "Sin país" para clientes sin país válido | 5 · Gold |
| `scripts/calcular_gold.py` | Ejecuta el SQL de Gold, comprueba que cuadre con Bronze y Silver y muestra el KPI contra la meta del 80 % | 5 · Gold |
| `scripts/registrar_monitoreo.py` | Escribe en `monitoreo_ejecuciones` una fila por stage (6 por ejecución), también si alguno falló o no corrió | 6 · Monitoreo |
| `scripts/metricas.py` | Cada stage publica sus métricas (estado, filas, horas) para el monitoreo | 1 a 5 |
| `scripts/db.py` | Conexión a Databricks con los 3 secrets, destino (`workspace.demo` por defecto) y `run_id` | 2 a 6 |
| `sql/permisos.sql` | `GRANT` por grupo según la matriz de acceso. **No lo ejecuta el pipeline**: en Free Edition no existen los grupos | — (manual, en un workspace real) |

Variables opcionales (no son secretos): `DATABRICKS_CATALOG` (por defecto `workspace`) y `DATABRICKS_SCHEMA` (por defecto `demo`).

### Cuándo corre

| Disparador | Rama | Para qué |
|---|---|---|
| Pull Request hacia `main` | La rama de la fase | Probar todo antes del merge |
| Lunes 6:00 a. m. hora de Lima (`cron: "0 11 * * 1"`, UTC) | `main` | Gold actualizada antes de las 8:00 |
| Manual: *Actions → Pipeline ClientesConfiables → Run workflow* | La que elijas | Recargar cuando haga falta |

- **El schedule se apaga solo:** en repos públicos, GitHub desactiva los workflows programados después de **60 días sin actividad** en el repo. Para reactivarlo: *Actions → Pipeline ClientesConfiables → Enable workflow*.
- **Alertas:** si el workflow falla, GitHub avisa por correo. En la carga programada avisa a quien modificó el `cron` por última vez.
- **Re-run:** *Re-run all jobs* es una ejecución nueva, con un `run_id` nuevo y su propia tanda en Bronze, rechazados y monitoreo. *Re-run failed jobs* reutiliza el `run_id` de la ingesta, así calidad y Gold leen la carga correcta.

### Cómo consultar el resultado

Todas las fechas están en **UTC**. Para verlas en hora de Lima: `from_utc_timestamp(col, 'America/Lima')`.

```sql
-- Indicador por país (lo que usa BI)
SELECT * FROM workspace.demo.gold_contactables_pais ORDER BY country_code;
```

```sql
-- Lista de contacto para Marketing (incluye emails: acceso restringido)
SELECT customer_id, name, email, country_code FROM workspace.demo.silver_customers WHERE es_contactable;
```

```sql
-- Qué corregir en el CRM
SELECT _row_number, customer_id, motivo FROM workspace.demo.rechazados_customers
WHERE _run_id = (SELECT MAX(_run_id) FROM workspace.demo.silver_customers) ORDER BY _row_number;
```

```sql
-- Estado de las últimas ejecuciones
SELECT run_id, stage, estado, mensaje, from_utc_timestamp(started_at, 'America/Lima') AS inicio_lima
FROM workspace.demo.monitoreo_ejecuciones ORDER BY started_at DESC LIMIT 30;
```

### Correr las pruebas en local

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -r requirements.txt
```

(En macOS o Linux, usa `.venv/bin/python` en lugar de `.venv/Scripts/python`.)

```bash
.venv/Scripts/python -m pytest
```

```bash
.venv/Scripts/python scripts/validar_csv.py
```

Los stages 2 a 6 están pensados para correr en GitHub Actions con los secrets. Para correrlos en local tendrías que exportar las 3 variables en tu terminal: nunca las guardes en un archivo del repo.

## Preguntas frecuentes

**¿Tengo que usar Databricks?** No. Si cambias de plataforma, actualiza `constitucion/stack-tecnologico.md` y las specs de cada feature siguen sirviendo.

**¿Qué pasa si el asistente escribe código antes de que apruebe la spec?** Detenlo y recuérdale la regla del prompt: primero preguntas, después spec, después código.

**¿Puedo editar la spec a mano?** Sí, y es buena práctica. La spec es tuya.

## Créditos

Taller del Módulo de Operaciones (DevSecOps / DataOps), UTEC Posgrado. Basado en el flujo de prompts de [Coding-Latam/taller-sdd-02](https://github.com/Coding-Latam/taller-sdd-02), adaptado a datos y al español.
