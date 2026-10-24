"""Conexión a Databricks y utilidades comunes de los stages que tocan el warehouse.

Las credenciales se leen solo de variables de entorno, que el workflow toma de
GitHub Secrets: DATABRICKS_HOST, DATABRICKS_HTTP_PATH y DATABRICKS_TOKEN.
Nunca se imprimen sus valores.

El destino se puede cambiar con DATABRICKS_CATALOG y DATABRICKS_SCHEMA
(no son secretos; por defecto: workspace y demo).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping

VARIABLES_REQUERIDAS = ("DATABRICKS_HOST", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN")
CATALOGO_POR_DEFECTO = "workspace"
SCHEMA_POR_DEFECTO = "demo"

_IDENTIFICADOR = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class ConfiguracionInvalida(RuntimeError):
    """Falta una variable de entorno o tiene un valor no permitido. El mensaje nunca incluye secretos."""


@dataclass(frozen=True)
class Configuracion:
    host: str
    http_path: str
    token: str

    def __repr__(self) -> str:  # evita que el token aparezca si alguien imprime el objeto
        return "Configuracion(host=***, http_path=***, token=***)"


def leer_configuracion(env: Mapping[str, str] | None = None) -> Configuracion:
    env = os.environ if env is None else env
    faltantes = [v for v in VARIABLES_REQUERIDAS if not (env.get(v) or "").strip()]
    if faltantes:
        raise ConfiguracionInvalida(
            f"Faltan variables de entorno: {', '.join(faltantes)}. "
            "Configúralas como GitHub Secrets del repo."
        )
    host = env["DATABRICKS_HOST"].strip().removeprefix("https://").removeprefix("http://").rstrip("/")
    return Configuracion(host, env["DATABRICKS_HTTP_PATH"].strip(), env["DATABRICKS_TOKEN"].strip())


def leer_destino(env: Mapping[str, str] | None = None) -> tuple[str, str]:
    """Catálogo y schema de destino. Solo se aceptan identificadores simples."""
    env = os.environ if env is None else env
    catalogo = (env.get("DATABRICKS_CATALOG") or CATALOGO_POR_DEFECTO).strip()
    schema = (env.get("DATABRICKS_SCHEMA") or SCHEMA_POR_DEFECTO).strip()
    for nombre, valor in (("DATABRICKS_CATALOG", catalogo), ("DATABRICKS_SCHEMA", schema)):
        if not _IDENTIFICADOR.fullmatch(valor):
            raise ConfiguracionInvalida(f"{nombre} debe ser un identificador simple (letras, números y _).")
    return catalogo, schema


def renderizar_sql(texto: str, catalogo: str, schema: str) -> str:
    """Reemplaza {{catalog}} y {{schema}} en un script SQL."""
    return texto.replace("{{catalog}}", catalogo).replace("{{schema}}", schema)


def run_id(env: Mapping[str, str] | None = None) -> str:
    """<github.run_id>-<github.run_attempt>, o un id local si no corre en GitHub Actions."""
    env = os.environ if env is None else env
    if env.get("GITHUB_RUN_ID"):
        return f"{env['GITHUB_RUN_ID']}-{env.get('GITHUB_RUN_ATTEMPT', '1')}"
    return "local-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def conectar(config: Configuracion):
    """Abre una conexión al SQL Warehouse."""
    from databricks import sql  # import diferido: los tests no necesitan el conector

    return sql.connect(
        server_hostname=config.host,
        http_path=config.http_path,
        access_token=config.token,
    )
