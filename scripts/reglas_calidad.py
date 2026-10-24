"""Reglas de calidad por fila de customers.csv.

Una sola fuente de verdad para las reglas: las usa el stage 1 (shift-left) para
reportar y, desde la Fase 2, el stage de calidad para mandar filas a rechazados.
No depende de Databricks.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

COLUMNAS = ("customer_id", "name", "age", "country", "email")

EDAD_MINIMA = 0
EDAD_MAXIMA = 120
MAYORIA_DE_EDAD = 18

SEPARADOR_MOTIVOS = "; "

# Motivos en el orden en que se registran cuando una fila tiene varios.
CUSTOMER_ID_VACIO = "customer_id_vacio"
NOMBRE_VACIO = "nombre_vacio"
EDAD_VACIA = "edad_vacia"
EDAD_NO_NUMERICA = "edad_no_numerica"
EDAD_FUERA_DE_RANGO = "edad_fuera_de_rango"
PAIS_VACIO = "pais_vacio"
PAIS_DESCONOCIDO = "pais_desconocido"
EMAIL_VACIO = "email_vacio"
EMAIL_INVALIDO = "email_invalido"
DUPLICADO = "duplicado"

MOTIVOS = (
    CUSTOMER_ID_VACIO,
    NOMBRE_VACIO,
    EDAD_VACIA,
    EDAD_NO_NUMERICA,
    EDAD_FUERA_DE_RANGO,
    PAIS_VACIO,
    PAIS_DESCONOCIDO,
    EMAIL_VACIO,
    EMAIL_INVALIDO,
    DUPLICADO,
)

_ENTERO = re.compile(r"-?\d+")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


@dataclass(frozen=True)
class ResultadoFila:
    """Resultado de evaluar una fila. Nunca guarda el email."""

    numero: int  # 1 = primera fila de datos (sin contar el encabezado)
    customer_id: str
    motivos: tuple[str, ...]
    es_menor_de_edad: bool  # solo puede ser True en filas válidas

    @property
    def es_valida(self) -> bool:
        return not self.motivos

    @property
    def motivo(self) -> str:
        return SEPARADOR_MOTIVOS.join(self.motivos)


def normalizar(fila: Mapping[str, str | None]) -> dict[str, str]:
    """Quita espacios al inicio y al final de todos los campos y pasa el país a mayúsculas."""
    limpia = {col: (fila.get(col) or "").strip() for col in COLUMNAS}
    limpia["country"] = limpia["country"].upper()
    return limpia


def motivo_customer_id(fila: Mapping[str, str]) -> str | None:
    return CUSTOMER_ID_VACIO if not fila["customer_id"] else None


def motivo_nombre(fila: Mapping[str, str]) -> str | None:
    return NOMBRE_VACIO if not fila["name"] else None


def motivo_edad(fila: Mapping[str, str]) -> str | None:
    edad = fila["age"]
    if not edad:
        return EDAD_VACIA
    if not _ENTERO.fullmatch(edad):
        return EDAD_NO_NUMERICA
    if not EDAD_MINIMA <= int(edad) <= EDAD_MAXIMA:
        return EDAD_FUERA_DE_RANGO
    return None


def motivo_pais(fila: Mapping[str, str], paises: set[str]) -> str | None:
    pais = fila["country"]
    if not pais:
        return PAIS_VACIO
    if pais not in paises:
        return PAIS_DESCONOCIDO
    return None


def motivo_email(fila: Mapping[str, str]) -> str | None:
    email = fila["email"]
    if not email:
        return EMAIL_VACIO
    if not _EMAIL.fullmatch(email):
        return EMAIL_INVALIDO
    return None


def evaluar_filas(filas: Iterable[Mapping[str, str | None]], paises: set[str]) -> list[ResultadoFila]:
    """Evalúa las filas en orden. Ante un customer_id repetido, manda la primera fila."""
    vistos: set[str] = set()
    resultados: list[ResultadoFila] = []

    for numero, original in enumerate(filas, start=1):
        fila = normalizar(original)
        motivos = [
            m
            for m in (
                motivo_customer_id(fila),
                motivo_nombre(fila),
                motivo_edad(fila),
                motivo_pais(fila, paises),
                motivo_email(fila),
            )
            if m
        ]

        customer_id = fila["customer_id"]
        if customer_id:
            if customer_id in vistos:
                motivos.append(DUPLICADO)
            vistos.add(customer_id)

        es_menor = not motivos and int(fila["age"]) < MAYORIA_DE_EDAD
        resultados.append(ResultadoFila(numero, customer_id, tuple(motivos), es_menor))

    return resultados


def cargar_paises(ruta: Path) -> set[str]:
    """Lee los códigos de país de data/reference/paises.csv."""
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        return {fila["country_code"].strip().upper() for fila in csv.DictReader(archivo)}
