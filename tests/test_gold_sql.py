"""Tests del stage 5 · Gold: revisión estática del SQL y lógica del script, sin Databricks."""

import json
import re
from decimal import Decimal

import calcular_gold as cg
import db
from conftest import ConexionFalsa, CursorFalso

SQL = cg.SQL_GOLD.read_text(encoding="utf-8")
CODIGO = "\n".join(l for l in SQL.splitlines() if not l.lstrip().startswith("--"))

GOLD_ESPERADO = [
    ("AR", "Argentina", "Sudamérica", 2, 1, Decimal("50.00")),
    ("CL", "Chile", "Sudamérica", 3, 1, Decimal("33.33")),
    ("CO", "Colombia", "Sudamérica", 2, 1, Decimal("50.00")),
    ("MX", "México", "Norteamérica", 2, 1, Decimal("50.00")),
    ("PE", "Perú", "Sudamérica", 10, 6, Decimal("60.00")),
    ("ZZ", "Sin país", "Sin región", 1, 0, Decimal("0.00")),
]


def test_sql_reemplaza_gold_completa_con_run_id():
    assert CODIGO.lstrip().startswith("INSERT OVERWRITE {{catalog}}.{{schema}}.gold_contactables_pais")
    assert CODIGO.count(":run_id") == 3  # Bronze, Silver y la columna _run_id


def test_sql_agrupa_sin_pais_en_zz():
    assert "'ZZ'" in CODIGO and "'Sin país'" in CODIGO and "'Sin región'" in CODIGO
    assert "rp.country_code IS NULL" in CODIGO


def test_sql_deduplica_como_las_reglas_de_calidad():
    assert re.search(r"ROW_NUMBER\(\) OVER \(PARTITION BY trim\(customer_id\) ORDER BY _row_number\)", CODIGO)
    assert "orden = 1" in CODIGO
    assert "upper(trim(coalesce(country, '')))" in CODIGO


def test_sql_usa_contactables_de_silver_y_no_toca_emails():
    assert "es_contactable" in CODIGO
    assert "email" not in CODIGO.lower()
    assert "DROP" not in CODIGO.upper()


def test_sql_columnas_en_el_orden_del_contrato():
    alias = re.findall(r"AS (\w+),?[ \t]*$", CODIGO.split("FROM (")[0], flags=re.M)
    assert alias == ["country_name", "region", "clientes_contactables", "pct_contactables", "_run_id", "_updated_at"]


def test_kpi_y_distancia_a_la_meta():
    assert cg.texto_kpi(10, 20) == "KPI 50,00 % · meta 80 % · faltan 30,00 puntos"
    assert cg.texto_kpi(17, 20) == "KPI 85,00 % · meta 80 % · meta cumplida"
    assert cg.texto_kpi(0, 0) == "KPI 0,00 % · meta 80 % · faltan 80,00 puntos"


def test_verificar_detecta_descuadres():
    assert cg.verificar((6, 20, 10), 20, 10) == []
    errores = cg.verificar((6, 19, 9), 20, 10)
    assert any("clientes_unicos" in e for e in errores)
    assert any("clientes_contactables" in e for e in errores)
    assert cg.verificar((0, 0, 0), 0, 0) == ["Gold quedó vacía para esta ejecución."]


def correr_main(monkeypatch, tmp_path, sumas_gold, unicos_bronze=20):
    cursor = CursorFalso(resultados=[[(12, 10)], [(unicos_bronze,)], [sumas_gold], GOLD_ESPERADO])
    monkeypatch.setattr(db, "conectar", lambda _: ConexionFalsa(cursor))
    monkeypatch.setenv("RUN_ID", "888-1")
    salida = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salida))
    resumen = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumen))
    codigo = cg.main()
    datos = json.loads(salida.read_text(encoding="utf-8").split("metricas=", 1)[1])
    return codigo, datos, cursor, resumen


def test_main_calcula_y_publica_el_kpi(monkeypatch, tmp_path, secrets_falsos):
    codigo, datos, cursor, resumen = correr_main(monkeypatch, tmp_path, (6, 20, 10))
    assert codigo == 0
    assert (datos["estado"], datos["filas_entrada"], datos["filas_salida"]) == ("exito", 12, 6)
    assert "KPI 50,00 %" in datos["mensaje"]
    assert any("INSERT OVERWRITE workspace.demo.gold_contactables_pais" in s for s in cursor.sentencias())
    assert all(p == {"run_id": "888-1"} for _, p in cursor.ejecutadas)
    texto = resumen.read_text(encoding="utf-8")
    assert "| ZZ | Sin país | Sin región | 1 | 0 | 0.00 |" in texto
    assert "@" not in texto


def test_main_falla_si_gold_no_cuadra(monkeypatch, tmp_path, capsys, secrets_falsos):
    codigo, datos, _, _ = correr_main(monkeypatch, tmp_path, (6, 19, 10))
    assert codigo == 1
    assert datos["estado"] == "fallo"
    assert "::error" in capsys.readouterr().out
