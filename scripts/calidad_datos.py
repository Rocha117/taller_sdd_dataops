"""Stage 4 · Calidad de datos.

Lee la carga de Bronze de esta ejecución, aplica las reglas de reglas_calidad.py
(las mismas del shift-left) y escribe:
- rechazados_customers: cada fila con al menos un motivo, con su registro original.
- silver_customers: las filas válidas, normalizadas y con banderas (reemplazo completo).

Con UMBRAL_RECHAZO_PCT (50 %) o más de rechazos: guarda los rechazados, NO toca
Silver (queda la última carga buena) y falla, así Gold no corre.
Nunca muestra emails en el log ni en el resumen del job.

Uso: python scripts/calidad_datos.py   (RUN_ID = el que publicó el stage 3)
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field

import db
import metricas
import reglas_calidad as rc

TAMANO_LOTE = 25

SQL_LEER_BRONZE = (
    "SELECT _row_number, customer_id, name, age, country, email "
    "FROM {{catalog}}.{{schema}}.bronze_customers WHERE _run_id = :run_id ORDER BY _row_number"
)
SQL_LEER_PAISES = "SELECT country_code FROM {{catalog}}.{{schema}}.ref_paises"
SQL_BORRAR_RECHAZADOS = "DELETE FROM {{catalog}}.{{schema}}.rechazados_customers WHERE _run_id = :run_id"
SQL_INSERTAR_RECHAZADOS = (
    "INSERT INTO {{catalog}}.{{schema}}.rechazados_customers "
    "(_run_id, _row_number, customer_id, registro_original, motivo, _rejected_at) VALUES "
)
SQL_SILVER = (
    "{modo} {{catalog}}.{{schema}}.silver_customers "
    "(customer_id, name, age, country_code, email, es_mayor_edad, es_contactable, _run_id, _processed_at) VALUES "
)
SQL_VACIAR_SILVER = "DELETE FROM {{catalog}}.{{schema}}.silver_customers"


@dataclass
class Clasificacion:
    total: int
    silver: list[dict] = field(default_factory=list)
    rechazados: list[dict] = field(default_factory=list)
    conteo_motivos: dict[str, int] = field(default_factory=dict)

    @property
    def pct_rechazo(self) -> float:
        return rc.pct_rechazo(len(self.rechazados), self.total)

    @property
    def supera_umbral(self) -> bool:
        return rc.supera_umbral(len(self.rechazados), self.total)

    @property
    def menores(self) -> list[str]:
        return [f["customer_id"] for f in self.silver if not f["es_mayor_edad"]]

    @property
    def contactables(self) -> int:
        return sum(1 for f in self.silver if f["es_contactable"])


def clasificar(filas_bronze: list[dict], paises: set[str]) -> Clasificacion:
    """Separa válidos y rechazados. Función pura: no toca Databricks."""
    resultados = rc.evaluar_filas(filas_bronze, paises)
    clasificacion = Clasificacion(total=len(filas_bronze))
    conteo: Counter[str] = Counter()

    for bronze, resultado in zip(filas_bronze, resultados):
        if resultado.es_valida:
            limpia = rc.normalizar(bronze)
            edad = int(limpia["age"])
            mayor = edad >= rc.MAYORIA_DE_EDAD
            clasificacion.silver.append(
                {
                    "customer_id": limpia["customer_id"],
                    "name": limpia["name"],
                    "age": edad,
                    "country_code": limpia["country"],
                    "email": limpia["email"],
                    "es_mayor_edad": mayor,
                    "es_contactable": mayor,  # toda fila de Silver ya es válida
                }
            )
        else:
            conteo.update(resultado.motivos)
            original = {col: bronze.get(col) or "" for col in rc.COLUMNAS}
            clasificacion.rechazados.append(
                {
                    "_row_number": int(bronze["_row_number"]),
                    "customer_id": resultado.customer_id or None,
                    "registro_original": json.dumps(original, ensure_ascii=False),
                    "motivo": resultado.motivo,
                }
            )

    clasificacion.conteo_motivos = {m: conteo.get(m, 0) for m in rc.MOTIVOS}
    return clasificacion


def _insertar_por_lotes(cursor, prefijo: str, filas: list[dict], marcadores_fila, extra: dict) -> None:
    for inicio in range(0, len(filas), TAMANO_LOTE):
        lote = filas[inicio : inicio + TAMANO_LOTE]
        valores, parametros = [], dict(extra)
        for i, fila in enumerate(lote):
            valores.append(marcadores_fila(i))
            # Los marcadores no empiezan con "_": _row_number se pasa como :row_number_N
            parametros.update({f"{k.lstrip('_')}_{i}": v for k, v in fila.items()})
        cursor.execute(prefijo + ", ".join(valores), parametros)
        prefijo = prefijo.replace("INSERT OVERWRITE", "INSERT INTO")  # solo el primer lote reemplaza


def escribir(cursor, clasificacion: Clasificacion, run_id: str, catalogo: str, schema: str) -> None:
    def sql(texto: str) -> str:
        return db.renderizar_sql(texto, catalogo, schema)

    cursor.execute(sql(SQL_BORRAR_RECHAZADOS), {"run_id": run_id})
    _insertar_por_lotes(
        cursor,
        sql(SQL_INSERTAR_RECHAZADOS),
        clasificacion.rechazados,
        lambda i: (
            f"(:run_id, CAST(:row_number_{i} AS INT), :customer_id_{i}, "
            f":registro_original_{i}, :motivo_{i}, current_timestamp())"
        ),
        {"run_id": run_id},
    )

    if clasificacion.supera_umbral:
        return  # Silver no se toca: queda la última carga buena

    if not clasificacion.silver:
        cursor.execute(sql(SQL_VACIAR_SILVER))
        return
    _insertar_por_lotes(
        cursor,
        sql(SQL_SILVER.replace("{modo}", "INSERT OVERWRITE")),
        clasificacion.silver,
        lambda i: (
            f"(:customer_id_{i}, :name_{i}, CAST(:age_{i} AS INT), :country_code_{i}, :email_{i}, "
            f":es_mayor_edad_{i}, :es_contactable_{i}, :run_id, current_timestamp())"
        ),
        {"run_id": run_id},
    )


def generar_resumen(c: Clasificacion) -> str:
    """Resumen en Markdown para el job. Sin emails ni filas completas."""
    lineas = [
        "## Calidad de datos · Bronze → Silver + rechazados",
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Filas de Bronze de la ejecución | {c.total} |",
        f"| Filas válidas (Silver) | {len(c.silver)} |",
        f"| Contactables | {c.contactables} |",
        f"| Menores de edad (no contactables) | {len(c.menores)} |",
        f"| Filas rechazadas | {len(c.rechazados)} |",
        f"| % rechazos | {metricas.pct_texto(c.pct_rechazo)} (umbral {rc.UMBRAL_RECHAZO_PCT} %) |",
        "",
        "| Motivo | Filas |",
        "|---|---|",
    ]
    lineas += [f"| `{m}` | {n} |" for m, n in c.conteo_motivos.items()]
    if c.rechazados:
        lineas += ["", "| Fila | customer_id | Motivos |", "|---|---|---|"]
        lineas += [f"| {r['_row_number']} | {r['customer_id'] or '(vacío)'} | {r['motivo']} |" for r in c.rechazados]
    if c.supera_umbral:
        lineas += ["", "❌ **Se superó el umbral: Silver no se actualizó y Gold no corre.**"]
    return "\n".join(lineas) + "\n"


def leer_entrada(cursor, run_id: str, catalogo: str, schema: str) -> tuple[list[dict], set[str]]:
    cursor.execute(db.renderizar_sql(SQL_LEER_BRONZE, catalogo, schema), {"run_id": run_id})
    columnas = ("_row_number",) + rc.COLUMNAS
    filas = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
    cursor.execute(db.renderizar_sql(SQL_LEER_PAISES, catalogo, schema))
    paises = {codigo.upper() for (codigo,) in cursor.fetchall()}
    return filas, paises


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    with metricas.registrar("calidad") as m:
        try:
            config = db.leer_configuracion()
            catalogo, schema = db.leer_destino()
            run_id = os.environ.get("RUN_ID") or db.run_id()
            print(f"Stage 4 · Calidad de datos · run_id {run_id}")

            with db.conectar(config) as conexion, conexion.cursor() as cursor:
                filas, paises = leer_entrada(cursor, run_id, catalogo, schema)
                if not filas:
                    raise RuntimeError(f"Bronze no tiene filas con el run_id {run_id}.")
                c = clasificar(filas, paises)
                escribir(cursor, c, run_id, catalogo, schema)
        except Exception as error:  # noqa: BLE001 - se reporta cualquier fallo y se bloquea el PR
            m.fallar(f"{type(error).__name__}: {error}")
            print(f"::error title=Calidad de datos::{m.mensaje}")
            return 1

        resumen = generar_resumen(c)
        print(resumen)
        destino = os.environ.get("GITHUB_STEP_SUMMARY")
        if destino:
            with open(destino, "a", encoding="utf-8") as archivo:
                archivo.write(resumen)

        m.filas_entrada, m.filas_rechazadas = c.total, len(c.rechazados)
        m.filas_salida = 0 if c.supera_umbral else len(c.silver)
        texto = f"{len(c.rechazados)} de {c.total} filas rechazadas ({metricas.pct_texto(c.pct_rechazo)})"

        if c.supera_umbral:
            m.fallar(f"{texto}; umbral {rc.UMBRAL_RECHAZO_PCT} %: Silver no se actualizó")
            print(f"::error title=Calidad de datos::{m.mensaje}")
            return 1
        if c.rechazados:
            m.advertir(texto)
            print(f"::warning title=Calidad de datos::{texto}. Detalle en el resumen del job.")
        else:
            m.mensaje = f"0 rechazos; {len(c.silver)} filas en Silver"
        return 0


if __name__ == "__main__":
    sys.exit(main())
