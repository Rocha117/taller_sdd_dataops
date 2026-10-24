"""Stage 1 · Calidad shift-left.

Valida data/source/customers.csv en el runner, antes de tocar Databricks:
- Chequeos estructurales: si alguno falla, termina con código 1 y bloquea el PR.
- Reglas por fila (reglas_calidad.py): con UMBRAL_RECHAZO_PCT (50 %) o más de filas
  con error, también bloquea; por debajo, solo advierte.

El reporte va al resumen del job (GITHUB_STEP_SUMMARY) o a la consola.
Nunca muestra emails ni filas completas: solo número de fila, customer_id y motivos.

Uso: python scripts/validar_csv.py [ruta_csv] [--paises ruta_paises]
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import metricas
from reglas_calidad import (
    COLUMNAS,
    MOTIVOS,
    UMBRAL_RECHAZO_PCT,
    ResultadoFila,
    cargar_paises,
    evaluar_filas,
    pct_rechazo,
    supera_umbral,
)

RAIZ = Path(__file__).resolve().parents[1]
CSV_POR_DEFECTO = RAIZ / "data" / "source" / "customers.csv"
PAISES_POR_DEFECTO = RAIZ / "data" / "reference" / "paises.csv"


@dataclass
class ResultadoValidacion:
    errores_estructurales: list[str] = field(default_factory=list)
    filas: list[ResultadoFila] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errores_estructurales

    @property
    def total_filas(self) -> int:
        return len(self.filas)

    @property
    def ids_unicos(self) -> int:
        return len({f.customer_id for f in self.filas if f.customer_id})

    @property
    def filas_con_error(self) -> list[ResultadoFila]:
        return [f for f in self.filas if not f.es_valida]

    @property
    def pct_filas_con_error(self) -> float:
        return pct_rechazo(len(self.filas_con_error), self.total_filas)

    @property
    def supera_umbral(self) -> bool:
        return supera_umbral(len(self.filas_con_error), self.total_filas)

    @property
    def menores_de_edad(self) -> list[ResultadoFila]:
        return [f for f in self.filas if f.es_menor_de_edad]

    def conteo_por_motivo(self) -> dict[str, int]:
        conteo = Counter(m for f in self.filas for m in f.motivos)
        return {m: conteo.get(m, 0) for m in MOTIVOS}


def leer_filas(ruta: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Aplica los chequeos estructurales. Devuelve (filas, errores)."""
    if not ruta.is_file():
        return [], [f"No existe el archivo {ruta.name}."]

    contenido = ruta.read_bytes()
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], [f"{ruta.name} no está codificado en UTF-8."]

    if not texto.strip():
        return [], [f"{ruta.name} está vacío."]

    lector = csv.reader(io.StringIO(texto, newline=""))
    encabezado = [col.strip() for col in next(lector)]
    if tuple(encabezado) != COLUMNAS:
        return [], [
            f"El encabezado debe ser exactamente '{','.join(COLUMNAS)}' (en ese orden) "
            f"y es '{','.join(encabezado)}'."
        ]

    filas: list[dict[str, str]] = []
    errores: list[str] = []
    for numero, valores in enumerate(lector, start=1):
        if len(valores) != len(COLUMNAS):
            errores.append(
                f"La fila {numero} tiene {len(valores)} campos y debe tener {len(COLUMNAS)}."
            )
            continue
        filas.append(dict(zip(COLUMNAS, valores)))

    if not filas and not errores:
        errores.append(f"{ruta.name} solo tiene encabezado: no hay filas de datos.")
    return filas, errores


def validar(ruta_csv: Path, ruta_paises: Path) -> ResultadoValidacion:
    filas, errores = leer_filas(ruta_csv)
    if errores:
        return ResultadoValidacion(errores_estructurales=errores)
    return ResultadoValidacion(filas=evaluar_filas(filas, cargar_paises(ruta_paises)))


_pct = metricas.pct_texto


def generar_reporte(resultado: ResultadoValidacion) -> str:
    """Reporte en Markdown. No incluye emails ni filas completas."""
    lineas = ["## Calidad shift-left · customers.csv", ""]

    if not resultado.ok:
        lineas += ["❌ **Chequeos estructurales fallidos** (bloquea el Pull Request):", ""]
        lineas += [f"- {error}" for error in resultado.errores_estructurales]
        return "\n".join(lineas) + "\n"

    lineas += [
        "✅ Chequeos estructurales correctos.",
        "",
        (
            f"❌ **{_pct(resultado.pct_filas_con_error)} de filas con error: llega al umbral de "
            f"{UMBRAL_RECHAZO_PCT} % y bloquea el Pull Request.**"
            if resultado.supera_umbral
            else f"Umbral: el Pull Request se bloquea con {UMBRAL_RECHAZO_PCT} % o más de filas con error."
        ),
        "",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Filas de datos | {resultado.total_filas} |",
        f"| customer_id únicos | {resultado.ids_unicos} |",
        f"| Filas con al menos un error | {len(resultado.filas_con_error)} |",
        f"| % filas con error | {_pct(resultado.pct_filas_con_error)} |",
        f"| Menores de edad (información, no contactables) | {len(resultado.menores_de_edad)} |",
        "",
        "### Conteo por motivo",
        "",
        "| Motivo | Filas |",
        "|---|---|",
    ]
    lineas += [f"| `{motivo}` | {n} |" for motivo, n in resultado.conteo_por_motivo().items()]

    if resultado.filas_con_error:
        lineas += [
            "",
            "### Filas con error",
            "",
            "| Fila | customer_id | Motivos |",
            "|---|---|---|",
        ]
        lineas += [
            f"| {f.numero} | {f.customer_id or '(vacío)'} | {f.motivo} |"
            for f in resultado.filas_con_error
        ]

    if resultado.menores_de_edad:
        lineas += [
            "",
            "### Menores de edad (válidos, no se contactan)",
            "",
            ", ".join(f.customer_id for f in resultado.menores_de_edad),
        ]

    return "\n".join(lineas) + "\n"


def publicar_reporte(reporte: str) -> None:
    # La consola de Windows no siempre usa UTF-8; así el reporte se imprime igual.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(reporte)
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if destino:
        with open(destino, "a", encoding="utf-8") as archivo:
            archivo.write(reporte)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage 1 · Calidad shift-left de customers.csv")
    parser.add_argument("csv", nargs="?", type=Path, default=CSV_POR_DEFECTO)
    parser.add_argument("--paises", type=Path, default=PAISES_POR_DEFECTO)
    args = parser.parse_args(argv)

    with metricas.registrar("shift_left") as m:
        resultado = validar(args.csv, args.paises)
        publicar_reporte(generar_reporte(resultado))

        if not resultado.ok:
            for error in resultado.errores_estructurales:
                print(f"::error title=Calidad shift-left::{error}")
            m.fallar("Chequeos estructurales fallidos: " + " ".join(resultado.errores_estructurales))
            return 1

        con_error = len(resultado.filas_con_error)
        m.filas_entrada = resultado.total_filas
        m.filas_salida = resultado.total_filas - con_error
        m.filas_rechazadas = con_error
        resumen = (
            f"{con_error} de {resultado.total_filas} filas tienen errores "
            f"de calidad ({_pct(resultado.pct_filas_con_error)})"
        )

        if resultado.supera_umbral:
            print(
                f"::error title=Calidad shift-left::{resumen}: llega al umbral de "
                f"{UMBRAL_RECHAZO_PCT} %. Se bloquea antes de tocar Databricks."
            )
            m.fallar(f"{resumen}; umbral {UMBRAL_RECHAZO_PCT} %")
            return 1

        if con_error:
            print(f"::warning title=Calidad shift-left::{resumen}. Detalle en el resumen del job.")
            m.advertir(resumen)
        return 0


if __name__ == "__main__":
    sys.exit(main())
