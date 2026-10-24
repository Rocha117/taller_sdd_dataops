# ClientesConfiables · Input del negocio

> Esto es lo que nos dijeron las personas interesadas (stakeholders) en reuniones con el equipo de datos. Es **la entrada** de la constitución: el asistente de IA lo lee antes de escribir la constitución (`constitucion/`). No es una spec: tiene vacíos y algunas tensiones entre áreas, y la spec tiene que resolverlas.

## Lo que nos pidieron

- **Carmen, de Marketing / CRM**, quiere enviar cada lunes una campaña por correo solo a clientes que se puedan contactar. Hoy le rebotan muchos correos y no sabe por qué. Su indicador es el **% de clientes contactables**. Para armar la lista necesita saber, sin hacer cálculos, si cada cliente es **mayor de edad**.
- **Raúl, de Ingeniería de Datos**, quiere un pipeline que nadie tenga que correr a mano, con el código versionado en GitHub y que se pueda volver a ejecutar sin duplicar datos. Hoy el equipo usa Databricks y GitHub Actions, pero no quiere quedar amarrado a ninguna herramienta. Pide dos cosas más: que las tablas se creen desde el código y no a mano, y que **nada llegue a `main` sin pasar todas las pruebas**: cada cambio en su propia rama, con Pull Request, y merge solo cuando el pipeline esté en verde. Quiere encontrar los errores de calidad lo antes posible, en el Pull Request, y no cuando el dato ya está en producción.
- **Patricia, de Gobierno de Datos y Seguridad**, recuerda que el email es un dato personal: no debe aparecer en las tablas de reportes y nadie debe ver credenciales en el código. Además, los **menores de edad no se contactan**. Quiere saber qué ejecución cargó cada dato. Ningún registro con errores debe llegar a las tablas limpias: los **registros rechazados se guardan aparte, con el motivo del rechazo**, para que alguien los revise y los corrija en el origen.
- **Andrés, de Analítica / BI**, necesita una tabla con el indicador por país (con el nombre del país y su región, no solo el código), actualizada antes de las 8:00 a. m. de cada lunes. Si el dato llega tarde o con errores, quiere enterarse antes que Carmen.

## Lo que sabemos del dato

- Fuente: `data/source/customers.csv`, exportado del CRM (columnas `customer_id`, `name`, `age`, `country`, `email`).
- `country` viene como código de 2 letras (PE, CL, CO, MX, AR). No existe todavía una tabla de referencia de países con su nombre y región.
- Viene con problemas conocidos: países vacíos, nombres vacíos, edades faltantes o no numéricas, correos mal formados y registros duplicados.

## Lo que completamos en clase

- ¿Cuál es la meta del indicador de Carmen? (por ejemplo, pasar de X % a Y %): pasar de 50 % (línea base del archivo actual: 10 de 20 clientes únicos) a 80 % de clientes contactables.
- Cuando hay un duplicado, ¿cuál registro manda?: el primero que aparece en el archivo. Los siguientes van a la tabla de rechazados con motivo "duplicado".
- ¿Qué pasa si una regla de calidad falla un lunes: se detiene la carga o se envía con advertencia?: si hay al menos un rechazo, la carga sigue con advertencia; si los rechazos llegan al 50 % o más de las filas, el stage de calidad falla y la carga se detiene. (Primero se propuso 30 %, pero el archivo actual ya tiene 43 % de filas con error y el pipeline nunca pasaría en verde.)
