"""Stage 6 · Monitoreo.

Corre siempre, después de los stages 1 a 5, aunque alguno haya fallado o no haya
corrido. Lee el resultado y las métricas de cada job (NEEDS_JSON = toJSON(needs))
y escribe en monitoreo_ejecuciones una fila por stage, más la suya: 6 filas.

- Idempotente para la misma ejecución: borra su run_id antes de insertar.
- Falla si no quedaron 6 filas.
- Termina en rojo si algún stage no terminó en verde: nunca oculta un fallo.
- Ningún mensaje contiene emails.

Uso: python scripts/registrar_monitoreo.py
"""

from __future__ import annotations

import json
import os
import sys

import db
import metricas

# (id del job en el workflow, nombre del stage en monitoreo_ejecuciones)
STAGES = (
    ("calidad-shift-left", "shift_left"),
    ("despliegue-modelo", "despliegue_modelo"),
    ("ingesta-bronze", "bronze"),
    ("calidad-datos", "calidad"),
    ("gold", "gold"),
)
TRIGGERS = {"pull_request": "pull_request", "schedule": "schedule", "workflow_dispatch": "manual"}
COLUMNAS = (
    "run_id", "stage", "estado", "filas_entrada", "filas_salida", "filas_rechazadas",
    "mensaje", "trigger", "git_sha", "started_at", "finished_at",
)

SQL_BORRAR = "DELETE FROM {{catalog}}.{{schema}}.monitoreo_ejecuciones WHERE run_id = :run_id"
SQL_CONTAR = "SELECT COUNT(*) FROM {{catalog}}.{{schema}}.monitoreo_ejecuciones WHERE run_id = :run_id"
SQL_INSERTAR = (
    "INSERT INTO {{catalog}}.{{schema}}.monitoreo_ejecuciones "
    "(run_id, stage, estado, filas_entrada, filas_salida, filas_rechazadas, mensaje, `trigger`, "
    "git_sha, started_at, finished_at) VALUES "
)


def traducir_trigger(evento: str) -> str:
    return TRIGGERS.get(evento, "manual")


def _fila_de_stage(stage: str, job: dict | None, ahora: str) -> tuple[dict, bool]:
    """Arma la fila de un stage. Devuelve (fila, terminó_en_verde)."""
    job = job or {}
    resultado = job.get("result", "skipped")
    try:
        datos = json.loads((job.get("outputs") or {}).get("metricas") or "{}")
    except json.JSONDecodeError:
        datos = {}

    fila = {
        "stage": stage,
        "estado": datos.get("estado", metricas.EXITO),
        "filas_entrada": datos.get("filas_entrada"),
        "filas_salida": datos.get("filas_salida"),
        "filas_rechazadas": datos.get("filas_rechazadas"),
        "mensaje": datos.get("mensaje") or "",
        "started_at": datos.get("started_at") or ahora,
        "finished_at": datos.get("finished_at"),
    }

    if resultado == "success":
        if not datos:
            fila["mensaje"] = "El job terminó en verde sin publicar métricas"
        return fila, True

    fila["estado"] = metricas.FALLO
    if resultado == "skipped":
        fila["mensaje"] = "No corrió: falló un stage anterior"
    elif not datos:
        fila["mensaje"] = f"El job terminó en {resultado} sin publicar métricas"
    elif not fila["mensaje"]:
        fila["mensaje"] = f"El job terminó en {resultado}"
    return fila, False


def armar_filas(needs: dict, run_id: str, evento: str, git_sha: str, ahora: str) -> tuple[list[dict], list[str]]:
    """Las 6 filas de monitoreo y la lista de stages que no terminaron en verde. Función pura."""
    filas, con_fallo = [], []
    for job_id, stage in STAGES:
        fila, en_verde = _fila_de_stage(stage, needs.get(job_id), ahora)
        filas.append(fila)
        if not en_verde:
            con_fallo.append(stage)

    filas.append(
        {
            "stage": "monitoreo",
            "estado": metricas.FALLO if con_fallo else metricas.EXITO,
            "filas_entrada": len(STAGES),
            "filas_salida": len(STAGES) + 1,
            "filas_rechazadas": len(con_fallo),
            "mensaje": (
                f"{len(con_fallo)} de {len(STAGES)} stages no terminaron en verde: {', '.join(con_fallo)}"
                if con_fallo
                else f"Los {len(STAGES)} stages terminaron en verde"
            ),
            "started_at": ahora,
            "finished_at": metricas.ahora_utc(),
        }
    )

    for fila in filas:
        fila.update(run_id=run_id, trigger=traducir_trigger(evento), git_sha=git_sha)
        fila["mensaje"] = metricas.sin_emails(fila["mensaje"])
    return filas, con_fallo


def run_id_de_la_ejecucion(needs: dict) -> str:
    """El run_id con el que se cargó Bronze (stage 3); si no corrió, el del intento actual."""
    return ((needs.get("ingesta-bronze") or {}).get("outputs") or {}).get("run_id") or db.run_id()


def escribir(cursor, filas: list[dict], catalogo: str, schema: str) -> int:
    run_id = filas[0]["run_id"]
    cursor.execute(db.renderizar_sql(SQL_BORRAR, catalogo, schema), {"run_id": run_id})
    valores, parametros = [], {"run_id": run_id}
    for i, fila in enumerate(filas):
        valores.append(
            f"(:run_id, :stage_{i}, :estado_{i}, CAST(:filas_entrada_{i} AS BIGINT), "
            f"CAST(:filas_salida_{i} AS BIGINT), CAST(:filas_rechazadas_{i} AS BIGINT), :mensaje_{i}, "
            f":trigger_{i}, :git_sha_{i}, CAST(:started_at_{i} AS TIMESTAMP), CAST(:finished_at_{i} AS TIMESTAMP))"
        )
        parametros.update({f"{col}_{i}": fila[col] for col in COLUMNAS if col != "run_id"})
    cursor.execute(db.renderizar_sql(SQL_INSERTAR, catalogo, schema) + ", ".join(valores), parametros)
    cursor.execute(db.renderizar_sql(SQL_CONTAR, catalogo, schema), {"run_id": run_id})
    return int(cursor.fetchone()[0])


def generar_resumen(filas: list[dict]) -> str:
    iconos = {metricas.EXITO: "✅", metricas.ADVERTENCIA: "⚠️", metricas.FALLO: "❌"}
    lineas = [
        f"## Monitoreo · run_id {filas[0]['run_id']} · {filas[0]['trigger']}",
        "",
        "| Stage | Estado | Entrada | Salida | Rechazadas | Mensaje |",
        "|---|---|---|---|---|---|",
    ]
    for f in filas:
        valores = [f.get(k) if f.get(k) is not None else "—" for k in ("filas_entrada", "filas_salida", "filas_rechazadas")]
        lineas.append(
            f"| `{f['stage']}` | {iconos.get(f['estado'], '')} {f['estado']} | "
            + " | ".join(str(v) for v in valores)
            + f" | {f['mensaje']} |"
        )
    return "\n".join(lineas) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ahora = metricas.ahora_utc()
    try:
        needs = json.loads(os.environ.get("NEEDS_JSON") or "{}")
        filas, con_fallo = armar_filas(
            needs,
            run_id_de_la_ejecucion(needs),
            os.environ.get("GITHUB_EVENT_NAME", ""),
            os.environ.get("GITHUB_SHA", "local"),
            ahora,
        )
        resumen = generar_resumen(filas)
        print(resumen)
        destino = os.environ.get("GITHUB_STEP_SUMMARY")
        if destino:
            with open(destino, "a", encoding="utf-8") as archivo:
                archivo.write(resumen)

        config = db.leer_configuracion()
        catalogo, schema = db.leer_destino()
        with db.conectar(config) as conexion, conexion.cursor() as cursor:
            escritas = escribir(cursor, filas, catalogo, schema)
        if escritas != len(filas):
            raise RuntimeError(f"monitoreo_ejecuciones tiene {escritas} filas para el run_id y se esperaban {len(filas)}.")
    except Exception as error:  # noqa: BLE001 - un fallo del registro bloquea el PR
        print(f"::error title=Monitoreo::{metricas.sin_emails(f'{type(error).__name__}: {error}')}")
        return 1

    print(f"  ✔ {escritas} filas en {catalogo}.{schema}.monitoreo_ejecuciones")
    if con_fallo:
        print(f"::error title=Monitoreo::Stages que no terminaron en verde: {', '.join(con_fallo)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
