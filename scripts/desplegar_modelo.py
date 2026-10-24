"""Stage 2 · Despliegue del modelo.

1. Ejecuta los scripts de sql/ddl/ en orden numérico: CREATE TABLE IF NOT EXISTS
   (01 a 06) y cambios posteriores con ALTER (07 en adelante). Nunca DROP.
2. Carga ref_paises desde data/reference/paises.csv con un MERGE parametrizado
   que solo actualiza si cambió el nombre o la región.
3. Verifica el modelo contra sql/contrato_modelo.json en information_schema.columns.

Si un paso falla, termina con código 1. Es idempotente: correrlo dos veces deja
el mismo resultado.

Uso: python scripts/desplegar_modelo.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import db
import metricas

RAIZ = Path(__file__).resolve().parents[1]
DIR_DDL = RAIZ / "sql" / "ddl"
CONTRATO = RAIZ / "sql" / "contrato_modelo.json"
PAISES = RAIZ / "data" / "reference" / "paises.csv"

SQL_MERGE_PAIS = """
MERGE INTO {{catalog}}.{{schema}}.ref_paises AS t
USING (SELECT :country_code AS country_code, :country_name AS country_name, :region AS region) AS s
ON t.country_code = s.country_code
WHEN MATCHED AND (t.country_name <> s.country_name OR t.region <> s.region)
  THEN UPDATE SET t.country_name = s.country_name, t.region = s.region
WHEN NOT MATCHED THEN INSERT (country_code, country_name, region)
  VALUES (s.country_code, s.country_name, s.region)
"""

SQL_COLUMNAS = """
SELECT table_name, column_name, full_data_type
FROM {{catalog}}.information_schema.columns
WHERE table_schema = :schema
"""


def archivos_ddl(directorio: Path = DIR_DDL) -> list[Path]:
    """Scripts DDL en orden numérico (01_..., 02_..., ...): CREATE y ALTER."""
    return sorted(directorio.glob("[0-9][0-9]_*.sql"))


def preparar_sentencia(texto: str) -> str:
    """Cada archivo DDL tiene una sola sentencia; se quita el ';' final."""
    return texto.strip().rstrip(";").strip()


def leer_paises(ruta: Path = PAISES) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return [{k: v.strip() for k, v in fila.items()} for fila in csv.DictReader(archivo)]


def leer_contrato(ruta: Path = CONTRATO) -> dict[str, dict[str, str]]:
    return json.loads(ruta.read_text(encoding="utf-8"))["tablas"]


def _normalizar_tipo(tipo: str) -> str:
    return tipo.replace(" ", "").upper()


def comparar_contrato(
    esperado: dict[str, dict[str, str]],
    real: dict[str, dict[str, str]],
) -> tuple[list[str], list[str]]:
    """Devuelve (diferencias que bloquean, columnas extra que solo advierten)."""
    errores: list[str] = []
    extras: list[str] = []
    for tabla, columnas in esperado.items():
        if tabla not in real:
            errores.append(f"Falta la tabla {tabla}.")
            continue
        for columna, tipo in columnas.items():
            tipo_real = real[tabla].get(columna)
            if tipo_real is None:
                errores.append(f"Falta la columna {tabla}.{columna}.")
            elif _normalizar_tipo(tipo_real) != _normalizar_tipo(tipo):
                errores.append(f"{tabla}.{columna} es {tipo_real} y el contrato dice {tipo}.")
        extras += [f"{tabla}.{c}" for c in real[tabla] if c not in columnas]
    return errores, extras


def leer_columnas_reales(cursor, catalogo: str, schema: str) -> dict[str, dict[str, str]]:
    cursor.execute(db.renderizar_sql(SQL_COLUMNAS, catalogo, schema), {"schema": schema})
    real: dict[str, dict[str, str]] = {}
    for tabla, columna, tipo in cursor.fetchall():
        real.setdefault(tabla.lower(), {})[columna.lower()] = tipo
    return real


def desplegar(cursor, catalogo: str, schema: str, m: metricas.Metricas | None = None) -> list[str]:
    """Ejecuta los tres pasos. Devuelve las advertencias; lanza excepción si algo bloquea."""
    destino = f"{catalogo}.{schema}"

    print(f"1/3 · Creando tablas en {destino}")
    for archivo in archivos_ddl():
        cursor.execute(preparar_sentencia(db.renderizar_sql(archivo.read_text(encoding="utf-8"), catalogo, schema)))
        print(f"  ✔ {archivo.name}")

    print(f"2/3 · Cargando {destino}.ref_paises desde {PAISES.relative_to(RAIZ).as_posix()}")
    paises = leer_paises()
    sentencia = db.renderizar_sql(SQL_MERGE_PAIS, catalogo, schema)
    for pais in paises:
        cursor.execute(sentencia, pais)
    cursor.execute(f"SELECT COUNT(*) FROM {destino}.ref_paises")
    filas_ref = cursor.fetchone()[0]
    print(f"  ✔ {len(paises)} países en el CSV · {filas_ref} filas en ref_paises")
    if m is not None:
        m.filas_salida = filas_ref

    print(f"3/3 · Verificando el modelo contra {CONTRATO.relative_to(RAIZ).as_posix()}")
    contrato = leer_contrato()
    errores, extras = comparar_contrato(contrato, leer_columnas_reales(cursor, catalogo, schema))
    if errores:
        raise RuntimeError("El modelo no cumple el contrato:\n" + "\n".join(f"  - {e}" for e in errores))
    print(f"  ✔ {len(contrato)} tablas y sus columnas coinciden con el contrato")

    return [f"Columna fuera del contrato: {c}" for c in extras]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with metricas.registrar("despliegue_modelo") as m:
        try:
            config = db.leer_configuracion()
            catalogo, schema = db.leer_destino()
            print(f"Stage 2 · Despliegue del modelo · run_id {db.run_id()}")
            with db.conectar(config) as conexion, conexion.cursor() as cursor:
                advertencias = desplegar(cursor, catalogo, schema, m)
        except Exception as error:  # noqa: BLE001 - se reporta cualquier fallo y se bloquea el PR
            m.fallar(f"{type(error).__name__}: {error}")
            print(f"::error title=Despliegue del modelo::{m.mensaje}")
            return 1

        for advertencia in advertencias:
            print(f"::warning title=Despliegue del modelo::{advertencia}")
        if advertencias:
            m.advertir("; ".join(advertencias))
        else:
            m.mensaje = f"Modelo desplegado y verificado; {m.filas_salida} filas en ref_paises"
        print("Despliegue del modelo terminado sin errores.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
