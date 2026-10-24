"""Métricas de cada stage para el stage 6 · Monitoreo.

Cada stage abre `registrar(stage)` y, al terminar (también si falla), publica la
salida de job `metricas` en GITHUB_OUTPUT con un JSON de una línea. El job
Monitoreo las lee con toJSON(needs) y las escribe en monitoreo_ejecuciones.
Fuera de GitHub Actions solo se imprimen.
"""

from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Iterator

EXITO = "exito"
ADVERTENCIA = "advertencia"
FALLO = "fallo"

_EMAIL = re.compile(r"[^\s@'\"]+@[^\s@'\"]+")


def ahora_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sin_emails(texto: str) -> str:
    """Oculta cualquier email (o resto de uno) antes de que llegue a un log o al monitoreo."""
    return _EMAIL.sub("[email oculto]", texto).replace("@", "[arroba]")


def pct_texto(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",") + " %"


@dataclass
class Metricas:
    stage: str
    estado: str = EXITO
    filas_entrada: int | None = None
    filas_salida: int | None = None
    filas_rechazadas: int | None = None
    mensaje: str = ""
    started_at: str = field(default_factory=ahora_utc)
    finished_at: str | None = None

    def advertir(self, mensaje: str) -> None:
        if self.estado != FALLO:
            self.estado = ADVERTENCIA
            self.mensaje = sin_emails(mensaje)

    def fallar(self, mensaje: str) -> None:
        self.estado = FALLO
        self.mensaje = sin_emails(mensaje)

    def como_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def publicar_salida(nombre: str, valor: str) -> None:
    """Escribe una salida de job (nombre=valor) en GITHUB_OUTPUT, si existe."""
    destino = os.environ.get("GITHUB_OUTPUT")
    if destino:
        with open(destino, "a", encoding="utf-8") as archivo:
            archivo.write(f"{nombre}={valor}\n")


@contextmanager
def registrar(stage: str) -> Iterator[Metricas]:
    metricas = Metricas(stage)
    try:
        yield metricas
    except BaseException as error:
        if metricas.estado != FALLO:
            metricas.fallar(f"{type(error).__name__}: {error}")
        raise
    finally:
        metricas.finished_at = ahora_utc()
        publicar_salida("metricas", metricas.como_json())
        print(f"Métricas del stage {stage}: {metricas.como_json()}")
