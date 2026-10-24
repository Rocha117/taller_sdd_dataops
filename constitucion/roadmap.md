# Roadmap · ClientesConfiables

> Parte de la constitución del proyecto. Responde **¿qué está planificado y en qué orden?** Son dos fases que, juntas, recorren todo el ciclo del dato:
>
> `Diseño → Build (Bronze → Silver → Gold) → Test → Deploy → Monitoring`
>
> Cada fase tiene su propia feature spec en `specs/AAAA-MM-DD-<fase>/`, su propia rama y su propio Pull Request. No hay fechas objetivo: solo importa el orden.

## Resumen

| Fase | Objetivo | Rama sugerida | Depende de |
|---|---|---|---|
| 1 · Diseño y calidad shift-left | Dejar el modelo de datos creado desde el código y el CSV validado en cada Pull Request | `feat/fase-1-diseno-shift-left` | Constitución aprobada |
| 2 · Pipeline de punta a punta | Llenar el modelo de Bronze a Gold con calidad, rechazados y monitoreo, con merge a `main` solo en verde | `feat/fase-2-pipeline-e2e` | Fase 1 mergeada en `main` |

---

## Fase 1 · Diseño y calidad shift-left

**Objetivo:** dejar el modelo lógico y físico creado en Databricks desde el código, y validar el archivo de origen en cada Pull Request antes de tocar Databricks.

**Ciclo del dato que cubre:** Diseño · Test (shift-left) · Deploy del modelo.

### Entrega
- Modelo lógico y físico documentado en la spec (refina el de [stack-tecnologico.md](stack-tecnologico.md#modelado)).
- Scripts SQL versionados que crean **todas** las tablas en `workspace.demo`: `bronze_customers`, `silver_customers`, `rechazados_customers`, `ref_paises`, `gold_contactables_pais` y `monitoreo_ejecuciones`.
- CSV de referencia de países (código, nombre y región) y su carga en `ref_paises`.
- Script de validación shift-left en Python, con tests automáticos.
- Workflow de GitHub Actions con los stages **1 · Calidad shift-left** y **2 · Despliegue del modelo**, disparado por Pull Request.
- README con la documentación de cada script (qué hace y en qué stage corre).

### Qué bloquea el Pull Request en esta fase
- **Bloquea:** falta una columna, el archivo está vacío, el encabezado está mal o un script SQL de creación de tablas falla.
- **Solo reporta (advertencia):** los errores por fila (nombres vacíos, edades inválidas, etc.), con su conteo en el resumen del job. Todavía no existen la ingesta ni el stage de rechazados que los procese.

### Hecho cuando
- Las 6 tablas existen en `workspace.demo` con las columnas y tipos de la spec, creadas por el pipeline y no a mano.
- Correr el despliegue dos veces no falla ni duplica datos en `ref_paises`.
- El stage shift-left corre primero en el Pull Request y está en verde con el CSV actual.
- Ambos stages quedan como checks obligatorios en el ruleset de `main`.
- El Pull Request de la Fase 1 se mergea a `main` con todos los stages en verde.

---

## Fase 2 · Pipeline de punta a punta

**Objetivo:** llevar el dato de Bronze a Gold con reglas de calidad, rechazados con motivo y monitoreo de cada stage, corriendo en cada Pull Request y cada lunes, con merge a `main` solo en verde.

**Ciclo del dato que cubre:** Build (Bronze → Silver → Gold) · Test (calidad de datos) · Deploy · Monitoring.

### Entrega
- Stage **3 · Ingesta a Bronze**: el CSV crudo con `run_id`, archivo de origen y número de fila.
- Stage **4 · Calidad de datos**: registros válidos a Silver (con `es_mayor_edad` y `es_contactable`) y registros con error a `rechazados_customers` con el registro original y el motivo. Falla con **50 % o más** de rechazos; con al menos uno queda como advertencia.
- Stage **5 · Gold**: `gold_contactables_pais` con nombre del país y región, solo mayores de edad como contactables, sin emails.
- Stage **6 · Monitoreo**: cada stage (incluidos los de la Fase 1) escribe su fila en `monitoreo_ejecuciones`, también cuando falla.
- Shift-left ampliado: aplica las mismas reglas por fila que el stage de calidad y bloquea el PR si los rechazos proyectados llegan al 50 %, antes de tocar Databricks.
- Carga programada los lunes a las 6:00 a. m. hora de Lima y ejecución manual.
- Idempotencia comprobada: correr dos veces el pipeline no duplica datos.
- README completo: el repo corre de punta a punta solo con los 3 secrets.

### Hecho cuando
- Con el CSV actual: 21 filas en Bronze por ejecución, 12 en Silver (10 contactables y 2 menores), 9 en rechazados con su motivo y un KPI global de **50 %** en Gold.
- Ningún registro con error llega a Silver ni a Gold, y Gold no tiene emails.
- Cada stage de cada ejecución tiene su fila en `monitoreo_ejecuciones`.
- Los 6 stages son checks obligatorios en el ruleset de `main`.
- El Pull Request de la Fase 2 se mergea a `main` con todos los stages en verde.

> Los números de "Hecho cuando" salen del archivo actual y de las reglas de la constitución. La spec de la Fase 2 los confirma regla por regla en su `validacion.md`.

---

## Después de las dos fases (fuera de este roadmap)

Ideas que no se construyen ahora, para no perderlas:
- Ambientes separados de desarrollo y producción.
- Alertas por Slack o Teams.
- Más fuentes de clientes además del CSV del CRM.
- Seguimiento del KPI semana a semana contra la meta del 80 %.
