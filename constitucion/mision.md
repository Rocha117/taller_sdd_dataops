# Misión · ClientesConfiables

> Parte de la constitución del proyecto. Responde **¿para qué existe este dato?** Se consulta en cada feature spec. Fuente: [`negocio/input-negocio.md`](../negocio/input-negocio.md).

## Problema de negocio

Marketing envía cada lunes una campaña por correo y muchos correos rebotan sin que nadie sepa por qué. El archivo de clientes que exporta el CRM (`data/source/customers.csv`) trae nombres vacíos, países vacíos, edades faltantes o no numéricas, correos mal formados, duplicados y menores de edad mezclados con adultos. Hoy no hay una fuente confiable que diga **a quién se puede contactar**.

ClientesConfiables convierte ese archivo en un producto de datos confiable, automático y trazable: separa los registros válidos de los que tienen errores (guardando el motivo), marca a cada cliente como contactable o no, y publica un indicador por país para el negocio.

## Audiencia

| Stakeholder | Área | Qué necesita | Qué recibe del proyecto |
|---|---|---|---|
| Carmen | Marketing / CRM | Lista de clientes contactables cada lunes, sin hacer cálculos | Tabla Silver con las banderas `es_mayor_edad` y `es_contactable` (incluye email, acceso restringido) |
| Raúl | Ingeniería de Datos | Pipeline automático, versionado, idempotente, tablas desde el código, nada a `main` sin pasar las pruebas | Repo con pipeline por stages en GitHub Actions y `main` protegida |
| Patricia | Gobierno de Datos y Seguridad | Email fuera de los reportes, sin credenciales en el código, menores no contactados, rechazados guardados con motivo, trazabilidad por ejecución | Tabla de rechazados, tabla de monitoreo, `run_id` en cada fila, Gold sin datos personales |
| Andrés | Analítica / BI | Indicador por país (con nombre y región) listo antes de las 8:00 a. m. de cada lunes, y enterarse primero si algo falla | Tabla Gold por país y alertas de GitHub Actions cuando el pipeline falla |

## Alcance

### Dentro del proyecto
- Una única fuente: `data/source/customers.csv` (columnas `customer_id`, `name`, `age`, `country`, `email`).
- Validación del archivo en cada Pull Request, antes de tocar Databricks (calidad shift-left).
- Modelo de datos medallion (Bronze, Silver, Gold), tabla de rechazados, tabla de referencia de países y tabla de monitoreo, creadas desde el código.
- Reglas de calidad y de negocio: rechazar registros con errores, marcar menores de edad, decidir qué duplicado se queda.
- Indicador de clientes contactables, global y por país.
- Ejecución automática cada lunes y en cada Pull Request, con registro de cada ejecución.

### Fuera del proyecto
- Enviar la campaña de correo (lo hace Marketing con su herramienta).
- Corregir los datos en el CRM de origen (el proyecto solo los reporta en la tabla de rechazados).
- Dashboards o visualizaciones (BI consume la tabla Gold con su propia herramienta).
- Otras fuentes de datos distintas de `customers.csv`.
- Ambientes separados de desarrollo y producción (ver [stack tecnológico](stack-tecnologico.md#limitaciones-aceptadas)).

## Definiciones del negocio

- **Cliente único:** un `customer_id` distinto en el archivo de origen. Ante un duplicado, **manda el primero que aparece** en el archivo; los siguientes van a rechazados con motivo `duplicado`.
- **Registro válido:** pasa todas las reglas de calidad (nombre, edad, país y email presentes y con formato correcto, y no es duplicado). Solo los válidos llegan a Silver.
- **Mayor de edad:** `age >= 18`. Ser menor **no es un error de calidad**, es una regla de negocio: el registro llega a Silver con `es_mayor_edad = false` y nunca se contacta.
- **Cliente contactable:** registro válido **y** mayor de edad **y** con email válido.

## Cómo se ve el éxito

### KPI principal: % de clientes contactables

```
% contactables = clientes contactables / clientes únicos del archivo de origen × 100
```

| | Valor |
|---|---|
| Línea base (archivo actual) | **50 %** (10 de 20 clientes únicos) |
| Meta | **80 %** |
| Dónde se publica | Tabla Gold (por país) y su suma global |

El proyecto no "sube" el KPI por sí solo: lo **mide** de forma confiable y, con la tabla de rechazados, le dice al equipo del CRM qué corregir en el origen para llegar a la meta.

### Indicadores de salud del producto

| Indicador | Meta |
|---|---|
| Puntualidad: Gold actualizada antes de las 8:00 a. m. (hora de Lima) cada lunes | 100 % de los lunes |
| Registros con error que llegan a Silver o Gold | 0 |
| Emails en la tabla Gold | 0 columnas con email |
| Rechazados con motivo registrado | 100 % |
| Ejecuciones con registro en la tabla de monitoreo | 100 % |
| Credenciales en el código del repo | 0 |

## Tensiones entre stakeholders y cómo se resolvieron

| Tensión | Decisión |
|---|---|
| Carmen necesita el email para la campaña; Patricia no quiere emails en reportes | El email vive solo en Silver (acceso restringido a Marketing e Ingeniería). Gold no tiene email: solo conteos y porcentajes por país. |
| Raúl usa Databricks pero no quiere amarrarse a una herramienta | Cada herramienta del stack tiene una alternativa documentada. Las specs describen prácticas, no productos. |
| Raúl quiere detectar errores en el Pull Request; Patricia quiere que los rechazados se guarden aparte | Ambas cosas: el stage shift-left valida el archivo en el PR, y el stage de calidad guarda cada registro rechazado con su motivo. |
| Andrés quiere el dato antes de las 8:00; el pipeline puede fallar por calidad | Carga programada a las 6:00 a. m. (2 horas de margen). Si falla, GitHub notifica antes de que Carmen use la lista. |
| En clase se acordó detener la carga si los rechazos superan el 30 %, pero el archivo actual tiene 43 % de filas con error | Advertencia desde el primer rechazo; el stage falla con **50 % o más** de filas rechazadas. Con 30 % el pipeline nunca pasaría en verde con el dato actual. |
