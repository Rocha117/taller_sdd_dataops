"""Tests del stage 3 · Ingesta a Bronze (scripts/ingestar_bronze.py), sin Databricks."""

import json

import pytest

import db
import ingestar_bronze as ib
import validar_csv as vc
from conftest import ConexionFalsa, CursorFalso

FILAS, _ = vc.leer_filas(vc.CSV_POR_DEFECTO)


def test_insert_conserva_el_dato_crudo():
    _, parametros = ib.construir_insert(FILAS, 1)
    fila_c008 = next(i for i, f in enumerate(FILAS) if f["customer_id"] == "C008")
    assert parametros[f"name_{fila_c008}"] == "  "
    assert parametros[f"age_{FILAS.index(next(f for f in FILAS if f['customer_id'] == 'C015'))}"] == "abc"


def test_insert_numera_desde_la_primera_fila_y_usa_marcadores():
    sql, parametros = ib.construir_insert(FILAS[:3], 1)
    assert [parametros[f"row_number_{i}"] for i in range(3)] == [1, 2, 3]
    assert sql.count("current_timestamp()") == 3
    assert "ana.torres" not in sql  # los valores van como parámetros, nunca en el SQL


def test_ingestar_borra_antes_de_insertar_y_cuenta():
    cursor = CursorFalso(resultados=[[(21,)]])
    assert ib.ingestar(cursor, FILAS, "123-1", "workspace", "demo") == 21
    sentencias = cursor.sentencias()
    assert sentencias[0].startswith("DELETE FROM workspace.demo.bronze_customers WHERE _run_id = :run_id")
    assert sentencias[1].startswith("INSERT INTO workspace.demo.bronze_customers")
    assert sentencias[-1].startswith("SELECT COUNT(*)")
    assert all(p["run_id"] == "123-1" for _, p in cursor.ejecutadas)


def test_ingestar_en_lotes(monkeypatch):
    monkeypatch.setattr(ib, "TAMANO_LOTE", 10)
    cursor = CursorFalso(resultados=[[(21,)]])
    ib.ingestar(cursor, FILAS, "123-1", "workspace", "demo")
    inserts = [p for sql, p in cursor.ejecutadas if sql.startswith("INSERT")]
    assert len(inserts) == 3
    assert inserts[2]["row_number_0"] == 21


def preparar_main(monkeypatch, tmp_path, conteo):
    cursor = CursorFalso(resultados=[[(conteo,)]])
    monkeypatch.setattr(db, "conectar", lambda _: ConexionFalsa(cursor))
    monkeypatch.setenv("GITHUB_RUN_ID", "555")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    salida = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salida))
    return salida


def leer_salidas(salida):
    return dict(l.split("=", 1) for l in salida.read_text(encoding="utf-8").splitlines())


def test_main_publica_run_id_y_metricas(monkeypatch, tmp_path, capsys, secrets_falsos):
    salida = preparar_main(monkeypatch, tmp_path, 21)
    assert ib.main() == 0
    salidas = leer_salidas(salida)
    assert salidas["run_id"] == "555-1"
    datos = json.loads(salidas["metricas"])
    assert (datos["stage"], datos["estado"], datos["filas_entrada"], datos["filas_salida"]) == ("bronze", "exito", 21, 21)
    assert "@" not in capsys.readouterr().out


def test_main_falla_si_el_conteo_no_cuadra(monkeypatch, tmp_path, capsys, secrets_falsos):
    salida = preparar_main(monkeypatch, tmp_path, 20)
    assert ib.main() == 1
    assert "::error" in capsys.readouterr().out
    assert json.loads(leer_salidas(salida)["metricas"])["estado"] == "fallo"


def test_main_sin_secrets_falla_sin_conectarse(monkeypatch):
    for variable in db.VARIABLES_REQUERIDAS:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(db, "conectar", lambda _: pytest.fail("no debe conectarse"))
    assert ib.main() == 1
