"""Stage 5 · Gold.

Ejecuta sql/transformaciones/gold_contactables_pais.sql (INSERT OVERWRITE) y
comprueba que Gold cuadre con Bronze y Silver de la ejecución:
- SUM(clientes_unicos)       = clientes únicos de Bronze
- SUM(clientes_contactables) = contactables de Silver
Si no cuadra, falla. Escribe el KPI global y la distancia a la meta del 80 %.

Uso: python scripts/calcular_gold.py   (RUN_ID = el que publicó el stage 3)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import db
import metricas

RAIZ = Path(__file__).resolve().parents[1]
SQL_GOLD = RAIZ / "sql" / "transformaciones" / "gold_contactables_pais.sql"
META_KPI_PCT = 80

SQL_UNICOS_BRONZE = (
    "SELECT COUNT(DISTINCT trim(customer_id)) FROM {{catalog}}.{{schema}}.bronze_customers "
    "WHERE _run_id = :run_id AND trim(coalesce(customer_id, '')) <> ''"
)
SQL_SILVER = (
    "SELECT COUNT(*), COALESCE(SUM(CASE WHEN es_contactable THEN 1 ELSE 0 END), 0) "
    "FROM {{catalog}}.{{schema}}.silver_customers WHERE _run_id = :run_id"
)
SQL_SUMAS_GOLD = (
    "SELECT COUNT(*), COALESCE(SUM(clientes_unicos), 0), COALESCE(SUM(clientes_contactables), 0) "
    "FROM {{catalog}}.{{schema}}.gold_contactables_pais WHERE _run_id = :run_id"
)
SQL_FILAS_GOLD = (
    "SELECT country_code, country_name, region, clientes_unicos, clientes_contactables, pct_contactables "
    "FROM {{catalog}}.{{schema}}.gold_contactables_pais WHERE _run_id = :run_id ORDER BY country_code"
)


def kpi_pct(contactables: int, unicos: int) -> float:
    return contactables / unicos * 100 if unicos else 0.0


def texto_kpi(contactables: int, unicos: int) -> str:
    valor = kpi_pct(contactables, unicos)
    distancia = META_KPI_PCT - valor
    estado = f"faltan {distancia:.2f} puntos".replace(".", ",") if distancia > 0 else "meta cumplida"
    return f"KPI {metricas.pct_texto(valor)} · meta {META_KPI_PCT} % · {estado}"


def verificar(sumas_gold: tuple[int, int, int], unicos_bronze: int, contactables_silver: int) -> list[str]:
    """Devuelve los errores de cuadre (vacío si Gold cuadra)."""
    filas, unicos, contactables = sumas_gold
    errores = []
    if filas == 0:
        errores.append("Gold quedó vacía para esta ejecución.")
    if unicos != unicos_bronze:
        errores.append(f"SUM(clientes_unicos) = {unicos} y Bronze tiene {unicos_bronze} clientes únicos.")
    if contactables != contactables_silver:
        errores.append(
            f"SUM(clientes_contactables) = {contactables} y Silver tiene {contactables_silver} contactables."
        )
    return errores


def generar_resumen(filas: list[tuple], unicos: int, contactables: int) -> str:
    lineas = [
        "## Gold · Clientes contactables por país",
        "",
        f"**{texto_kpi(contactables, unicos)}** ({contactables} de {unicos} clientes únicos)",
        "",
        "| País | Nombre | Región | Únicos | Contactables | % |",
        "|---|---|---|---|---|---|",
    ]
    lineas += [f"| {c} | {n} | {r} | {u} | {k} | {p} |" for c, n, r, u, k, p in filas]
    return "\n".join(lineas) + "\n"


def calcular(cursor, run_id: str, catalogo: str, schema: str, m: metricas.Metricas) -> tuple[str, str]:
    def ejecutar(sql: str):
        cursor.execute(db.renderizar_sql(sql, catalogo, schema), {"run_id": run_id})

    ejecutar(SQL_SILVER)
    filas_silver, contactables_silver = (int(v) for v in cursor.fetchone())
    m.filas_entrada = filas_silver

    ejecutar(SQL_GOLD.read_text(encoding="utf-8").strip().rstrip(";"))

    ejecutar(SQL_UNICOS_BRONZE)
    unicos_bronze = int(cursor.fetchone()[0])
    ejecutar(SQL_SUMAS_GOLD)
    sumas = tuple(int(v) for v in cursor.fetchone())
    m.filas_salida = sumas[0]

    errores = verificar(sumas, unicos_bronze, contactables_silver)
    if errores:
        raise RuntimeError("Gold no cuadra: " + " ".join(errores))

    ejecutar(SQL_FILAS_GOLD)
    resumen = generar_resumen(cursor.fetchall(), sumas[1], sumas[2])
    return texto_kpi(sumas[2], sumas[1]), resumen


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with metricas.registrar("gold") as m:
        try:
            config = db.leer_configuracion()
            catalogo, schema = db.leer_destino()
            run_id = os.environ.get("RUN_ID") or db.run_id()
            print(f"Stage 5 · Gold · run_id {run_id}")
            with db.conectar(config) as conexion, conexion.cursor() as cursor:
                kpi, resumen = calcular(cursor, run_id, catalogo, schema, m)
        except Exception as error:  # noqa: BLE001 - se reporta cualquier fallo y se bloquea el PR
            m.fallar(f"{type(error).__name__}: {error}")
            print(f"::error title=Gold::{m.mensaje}")
            return 1

        print(resumen)
        destino = os.environ.get("GITHUB_STEP_SUMMARY")
        if destino:
            with open(destino, "a", encoding="utf-8") as archivo:
                archivo.write(resumen)
        m.mensaje = f"{m.filas_salida} filas en Gold; {kpi}"
        print(f"  ✔ {m.mensaje}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
