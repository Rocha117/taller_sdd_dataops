"""Utilidades comunes de los tests. Ningún test se conecta a Databricks."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def sin_salidas_de_github(monkeypatch):
    """Evita que los tests escriban en el resumen o en las salidas del job real de CI."""
    for variable in ("GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY", "RUN_ID"):
        monkeypatch.delenv(variable, raising=False)


class CursorFalso:
    """Registra cada execute y devuelve resultados preparados, en orden."""

    def __init__(self, resultados=None):
        self.ejecutadas: list[tuple[str, dict | None]] = []
        self._resultados = list(resultados or [])
        self._actual = None

    def execute(self, sql, parametros=None):
        self.ejecutadas.append((" ".join(sql.split()), parametros))
        sql_mayus = sql.lstrip().upper()
        if sql_mayus.startswith("SELECT") or sql_mayus.startswith("WITH"):
            self._actual = self._resultados.pop(0)

    def fetchall(self):
        return self._actual

    def fetchone(self):
        return self._actual[0]

    def sentencias(self):
        return [sql for sql, _ in self.ejecutadas]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ConexionFalsa:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def secrets_falsos(monkeypatch):
    monkeypatch.setenv("DATABRICKS_HOST", "dbc-test.cloud.databricks.com")
    monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/test")
    monkeypatch.setenv("DATABRICKS_TOKEN", "token-de-prueba")
