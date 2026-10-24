"""Stage 3 · Ingesta a Bronze.

Carga data/source/customers.csv tal cual llega (sin quitar espacios ni corregir
nada) en bronze_customers, con _run_id, archivo de origen y número de fila.

- Idempotente para la misma ejecución: borra su _run_id antes de insertar.
- INSERT parametrizado por lotes; nunca concatena valores en el SQL.
- Falla si las filas cargadas no coinciden con las del archivo.
- Publica el run_id para los stages 4, 5 y 6.
- El log solo muestra conteos: nunca filas ni emails.

Uso: python scripts/ingestar_bronze.py
"""

from __future__ import annotations

import sys

import db
import metricas
import validar_csv
from reglas_calidad import COLUMNAS

FUENTE = "data/source/customers.csv"
TAMANO_LOTE = 25  # filas por INSERT (7 parámetros por fila)

SQL_BORRAR = "DELETE FROM {{catalog}}.{{schema}}.bronze_customers WHERE _run_id = :run_id"
SQL_CONTAR = "SELECT COUNT(*) FROM {{catalog}}.{{schema}}.bronze_customers WHERE _run_id = :run_id"
SQL_INSERTAR = (
    "INSERT INTO {{catalog}}.{{schema}}.bronze_customers "
    "(customer_id, name, age, country, email, _run_id, _source_file, _row_number, _ingested_at) VALUES "
)


def construir_insert(filas: list[dict[str, str]], primera_fila: int) -> tuple[str, dict[str, object]]:
    """Arma un INSERT de varias filas con marcadores :nombre. _row_number empieza en primera_fila."""
    valores = []
    parametros: dict[str, object] = {}
    for i, fila in enumerate(filas):
        marcadores = []
        for columna in COLUMNAS:
            parametros[f"{columna}_{i}"] = fila[columna]  # crudo: se conservan los espacios
            marcadores.append(f":{columna}_{i}")
        parametros[f"row_number_{i}"] = primera_fila + i
        valores.append(
            "(" + ", ".join(marcadores)
            + f", :run_id, :source_file, CAST(:row_number_{i} AS INT), current_timestamp())"
        )
    return SQL_INSERTAR + ", ".join(valores), parametros


def ingestar(cursor, filas: list[dict[str, str]], run_id: str, catalogo: str, schema: str) -> int:
    """Borra la carga de este run_id, inserta las filas y devuelve cuántas quedaron."""
    cursor.execute(db.renderizar_sql(SQL_BORRAR, catalogo, schema), {"run_id": run_id})
    for inicio in range(0, len(filas), TAMANO_LOTE):
        sql, parametros = construir_insert(filas[inicio : inicio + TAMANO_LOTE], inicio + 1)
        parametros.update(run_id=run_id, source_file=FUENTE)
        cursor.execute(db.renderizar_sql(sql, catalogo, schema), parametros)
    cursor.execute(db.renderizar_sql(SQL_CONTAR, catalogo, schema), {"run_id": run_id})
    return int(cursor.fetchone()[0])


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with metricas.registrar("bronze") as m:
        try:
            filas, errores = validar_csv.leer_filas(validar_csv.CSV_POR_DEFECTO)
            if errores:
                raise RuntimeError("El archivo no pasa los chequeos estructurales: " + " ".join(errores))
            m.filas_entrada = len(filas)

            config = db.leer_configuracion()
            catalogo, schema = db.leer_destino()
            run_id = db.run_id()
            metricas.publicar_salida("run_id", run_id)
            print(f"Stage 3 · Ingesta a Bronze · run_id {run_id} · {len(filas)} filas en {FUENTE}")

            with db.conectar(config) as conexion, conexion.cursor() as cursor:
                cargadas = ingestar(cursor, filas, run_id, catalogo, schema)
            m.filas_salida = cargadas

            if cargadas != len(filas):
                raise RuntimeError(
                    f"Bronze tiene {cargadas} filas con el run_id {run_id} y el archivo tiene {len(filas)}."
                )
        except Exception as error:  # noqa: BLE001 - se reporta cualquier fallo y se bloquea el PR
            m.fallar(f"{type(error).__name__}: {error}")
            print(f"::error title=Ingesta a Bronze::{m.mensaje}")
            return 1

        m.mensaje = f"{cargadas} filas cargadas en {catalogo}.{schema}.bronze_customers"
        print(f"  ✔ {m.mensaje}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
