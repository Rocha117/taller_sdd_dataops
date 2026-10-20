# Prompts del taller SDD para Datos

Copia cada prompt tal cual en tu asistente de IA, abierto dentro de la carpeta del repo. Las partes entre `[corchetes]` las completamos **juntos en clase** antes de pegar el prompt.

---

## Prompt 1 · Constitución

> Se usa **una sola vez**, al inicio del proyecto. Responde a las tres preguntas de la constitución: Misión (¿por qué?), Stack tecnológico (¿cómo encaja con la tecnología?) y Roadmap (¿qué está planificado?).

```text
Actúa como arquitecto/a de datos de nuestro equipo. Vamos a construir
ClientesConfiables, un producto de datos a partir del archivo
data/source/customers.csv (columnas: customer_id, name, age, country, email).
Lee negocio/input-negocio.md: ahí está lo que pidieron los stakeholders.

Queremos crear la "constitución" del proyecto en la carpeta constitucion/. Es la
base de conocimiento del proyecto: se escribe una vez y se consulta en cada
feature. Crea estos tres archivos en español:

1. constitucion/mision.md
   - El PARA QUÉ del dato: problema de negocio, audiencia y alcance.
   - Qué queda dentro y qué queda fuera del proyecto.
   - Cómo se ve el éxito (KPI medible).

2. constitucion/stack-tecnologico.md
   - Plataforma: Databricks SQL Warehouse (schema "demo").
   - Orquestación y CI/CD: GitHub Actions, con credenciales solo en GitHub Secrets.
   - Lenguajes: SQL y Python.
   - Arquitectura medallion: Bronze (crudo), Silver (limpio), Gold (métricas),
     más una tabla de rechazados y una tabla de referencia de países.
   - Modelado: modelo lógico (entidades y relaciones) y físico (tablas, columnas,
     tipos y columnas derivadas como banderas). Las tablas se crean en
     Databricks desde el código versionado, nunca a mano.
   - Versionamiento y ramas: main está protegida; cada fase se trabaja en su
     propia rama con Pull Request, y solo se hace merge a main cuando todos los
     stages del pipeline pasan en verde.
   - Pipeline por stages, en este orden:
     1. Calidad shift-left: en cada Pull Request, antes de tocar Databricks,
        valida el archivo de origen (columnas, tipos y reglas de calidad).
     2. Despliegue del modelo: crea o actualiza las tablas.
     3. Ingesta a Bronze.
     4. Calidad de datos: los registros válidos pasan a Silver y los que
        tienen errores van a la tabla de rechazados, con el motivo. Si los
        rechazos superan el umbral que defina la spec, el stage falla.
     5. Gold: métricas para el negocio.
     6. Monitoreo: cada stage deja registro de su ejecución.
   - Listo para ejecutar: al terminar las dos fases, el repo debe correr de
     punta a punta con solo configurar los 3 secrets de GitHub. Cada script
     debe quedar documentado en el README (qué hace y en qué stage corre).
   - Restricciones de gobierno y calidad: datos personales (email), quién puede
     ver qué, reglas mínimas de calidad y trazabilidad de cada ejecución.
   - Para cada herramienta, indica una alternativa equivalente (comercial u
     open source). Ninguna herramienta es obligatoria; lo que importa es la
     práctica que cubre.

3. constitucion/roadmap.md
   - Solo DOS fases, en este orden, que juntas recorran todo el ciclo del dato:
     Fase 1 · Diseño y calidad shift-left: modelo lógico y físico, creación de
       las tablas en Databricks y validación del archivo en el Pull Request.
     Fase 2 · Pipeline de punta a punta: ingesta a Bronze, calidad de datos
       (Silver + rechazados), Gold y monitoreo, con merge a main solo en verde.
   - Cada fase con: objetivo en una línea, qué entrega y de qué fase depende.

Reglas:
- ANTES de escribir cualquier archivo, hazme todas las preguntas que necesites,
  agrupadas en tres bloques: Misión, Stack tecnológico y Roadmap. Espera mis
  respuestas.
- No escribas código ni crees el pipeline todavía. Solo la constitución.
- Si algo del input del negocio es ambiguo o dos stakeholders piden cosas que
  chocan, pregúntalo en vez de suponerlo.
- Al terminar, muéstrame un resumen de cada archivo para que yo lo apruebe.
```

**¿Qué completamos juntos en clase?** Antes de pegar el prompt, llenamos la sección "Lo que completamos en clase" de [`negocio/input-negocio.md`](negocio/input-negocio.md): la meta del indicador, qué registro manda ante un duplicado y qué pasa si falla una regla de calidad. También conviene detectar en grupo las tensiones: Raúl usa Databricks pero no quiere amarrarse; Andrés quiere el dato a las 8:00 y Patricia no quiere emails en reportes; Raúl quiere detectar errores en el Pull Request y Patricia quiere que los rechazados se guarden aparte.

✅ **Resultado esperado:** tres archivos en `constitucion/` y un roadmap con 2 fases que, juntas, cubren todo el ciclo del dato.

---

## Prompt 2 · Feature Spec

> Se usa **una vez por cada fase** del roadmap. Traduce una idea en algo construible: Scope (¿qué construye?), Requirements (restricciones que importan) y Validation (¿cómo sabemos que ya está listo?).

```text
Lee constitucion/roadmap.md y toma la siguiente fase que aún no tenga carpeta en specs/.
Crea una rama de git para esa fase (nunca trabajes directo en main).

Luego crea una carpeta specs/AAAA-MM-DD-nombre-de-la-fase/ (con la fecha de hoy)
y dentro estos tres archivos en español:

1. requerimientos.md
   - Scope: qué construye esta fase y qué NO construye.
   - Datos de entrada y de salida: tablas, columnas y tipos (contrato del dato).
   - Modelo de datos: columnas derivadas (por ejemplo, una bandera de mayor de
     edad) y tablas de referencia (por ejemplo, países con nombre y región).
     Incluye el script que crea cada tabla en Databricks.
   - Rechazados: qué reglas mandan un registro a la tabla de rechazados, qué
     columnas guarda (registro original, motivo, ejecución, fecha) y el umbral
     que hace fallar el stage de calidad.
   - Reglas de datos: qué hacer con nulos, duplicados, formatos inválidos y
     valores fuera de rango (por ejemplo: rechazar, marcar con una bandera o
     corregir).
   - Restricciones: seguridad (credenciales solo en secrets, datos personales),
     costo, idempotencia (correr dos veces no duplica datos) y trazabilidad
     (cada ejecución deja registro).
   - Decisiones tomadas y su motivo.

2. plan.md
   - Grupos de tareas numerados y pequeños, en el orden en que se construyen.
   - Cada tarea indica qué archivo crea o modifica.

3. validacion.md
   - Criterios de aceptación medibles, como una lista de casillas [ ].
   - Para cada criterio: cómo se comprueba (consulta SQL, test automático o
     revisión en GitHub Actions), en qué stage del pipeline corre y cuál es el
     resultado esperado.
   - Qué resultado bloquea el merge y cuál solo genera una advertencia.

Usa como guía constitucion/mision.md y constitucion/stack-tecnologico.md. Si esta fase
contradice algo de la constitución, avísame antes de seguir.

Reglas:
- ANTES de escribir cualquier archivo, hazme todas las preguntas que necesites,
  agrupadas en tres bloques: Scope, Requerimientos y Validación. Espera mis
  respuestas.
- No escribas código del pipeline todavía. Solo la spec de esta fase.
- Al terminar, muéstrame un resumen de los tres archivos para que yo lo apruebe.
```

**¿Qué completamos juntos en clase?** Las respuestas a las preguntas del asistente. Para definir las reglas de calidad conviene discutir en grupo:

| Pregunta | Qué conversar |
|---|---|
| ¿Qué hacemos con un nombre vacío? | ¿Se rechaza la fila o se marca y se deja pasar? |
| ¿Y con un menor de edad? | ¿Es error de calidad o es una regla de negocio de la misión? |
| ¿Y con un email mal formado? | ¿Afecta al KPI de clientes contactables? |
| ¿Y con un duplicado? | ¿Cuál fila se queda? |
| ¿Y con un país vacío o desconocido? | ¿Se rechaza o va como "Sin país"? ¿Qué dice la tabla de países? |
| ¿Dónde se calcula la bandera de mayor de edad? | ¿En Silver, para que la use cualquier reporte, o solo en Gold? |
| ¿Qué guarda la tabla de rechazados? | ¿Registro original, motivo, ejecución? ¿Cuántos rechazos hacen fallar el stage? |
| ¿Cuándo está "listo"? | ¿Qué número exacto debe dar cada consulta de validación? |

✅ **Resultado esperado:** una carpeta `specs/AAAA-MM-DD-<fase>/` con `requerimientos.md`, `plan.md` y `validacion.md`, y una rama de git para esa fase.

---

## Prompt 3 · Construir desde la spec

> Se usa **después de aprobar** la feature spec de una fase.

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

✅ **Resultado esperado:** el workflow corre en verde en GitHub Actions y cada casilla de `validacion.md` se puede comprobar.
