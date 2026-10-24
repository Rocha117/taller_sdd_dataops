"""Tests del stage 1 · Calidad shift-left (scripts/validar_csv.py)."""

from pathlib import Path

import pytest

import validar_csv as vc

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "fixture, mensaje",
    [
        ("falta_columna.csv", "encabezado"),
        ("encabezado_desordenado.csv", "encabezado"),
        ("solo_encabezado.csv", "solo tiene encabezado"),
        ("vacio.csv", "está vacío"),
        ("fila_incompleta.csv", "La fila 2 tiene 4 campos"),
    ],
)
def test_chequeos_estructurales_bloquean(fixture, mensaje, capsys):
    resultado = vc.validar(FIXTURES / fixture, vc.PAISES_POR_DEFECTO)
    assert not resultado.ok
    assert any(mensaje in e for e in resultado.errores_estructurales)
    assert vc.main([str(FIXTURES / fixture)]) == 1
    assert "::error" in capsys.readouterr().out


def test_archivo_inexistente_bloquea(tmp_path):
    assert vc.main([str(tmp_path / "no_existe.csv")]) == 1


def test_archivo_no_utf8_bloquea(tmp_path):
    ruta = tmp_path / "latin1.csv"
    ruta.write_bytes("customer_id,name,age,country,email\nC001,Pedro Huamán,39,PE,p@mail.com\n".encode("latin-1"))
    resultado = vc.validar(ruta, vc.PAISES_POR_DEFECTO)
    assert resultado.errores_estructurales == ["latin1.csv no está codificado en UTF-8."]


def test_archivo_con_bom_es_valido(tmp_path):
    ruta = tmp_path / "bom.csv"
    ruta.write_bytes((FIXTURES / "valido_minimo.csv").read_bytes().replace(b"customer_id", b"\xef\xbb\xbfcustomer_id", 1))
    assert vc.validar(ruta, vc.PAISES_POR_DEFECTO).ok


def test_valido_minimo_pasa_sin_advertencias(capsys):
    assert vc.main([str(FIXTURES / "valido_minimo.csv")]) == 0
    salida = capsys.readouterr().out
    assert "::warning" not in salida
    assert "::error" not in salida


def test_customers_csv_real_da_los_numeros_de_la_spec():
    """Valores esperados de specs/2026-10-23-fase-1-diseno-shift-left/validacion.md."""
    resultado = vc.validar(vc.CSV_POR_DEFECTO, vc.PAISES_POR_DEFECTO)

    assert resultado.ok
    assert resultado.total_filas == 21
    assert resultado.ids_unicos == 20
    assert len(resultado.filas_con_error) == 9
    assert round(resultado.pct_filas_con_error, 2) == 42.86
    assert [f.customer_id for f in resultado.menores_de_edad] == ["C004", "C009"]
    assert resultado.conteo_por_motivo() == {
        "customer_id_vacio": 0,
        "nombre_vacio": 2,
        "edad_vacia": 1,
        "edad_no_numerica": 1,
        "edad_fuera_de_rango": 0,
        "pais_vacio": 1,
        "pais_desconocido": 0,
        "email_vacio": 1,
        "email_invalido": 2,
        "duplicado": 1,
    }
    assert {(f.numero, f.customer_id, f.motivo) for f in resultado.filas_con_error} == {
        (3, "C003", "nombre_vacio"),
        (5, "C005", "email_invalido"),
        (8, "C008", "nombre_vacio"),
        (11, "C010", "duplicado"),
        (12, "C011", "email_invalido"),
        (13, "C012", "edad_vacia"),
        (16, "C015", "edad_no_numerica"),
        (17, "C016", "pais_vacio"),
        (20, "C019", "email_vacio"),
    }


def test_customers_csv_real_solo_advierte(capsys):
    assert vc.main([]) == 0
    salida = capsys.readouterr().out
    assert "::warning" in salida
    assert "9 de 21 filas" in salida
    assert "42,86 %" in salida


def test_reporte_nunca_muestra_emails(tmp_path, monkeypatch, capsys):
    resumen = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumen))
    vc.main([])
    assert "@" not in capsys.readouterr().out
    assert "@" not in resumen.read_text(encoding="utf-8")


def test_reporte_estructural_no_muestra_emails(capsys):
    vc.main([str(FIXTURES / "fila_incompleta.csv")])
    assert "@" not in capsys.readouterr().out


def test_reporte_se_escribe_en_el_resumen_del_job(tmp_path, monkeypatch):
    resumen = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumen))
    vc.main([])
    contenido = resumen.read_text(encoding="utf-8")
    assert "## Calidad shift-left" in contenido
    assert "| 11 | C010 | duplicado |" in contenido


# --- Fase 2: umbral de rechazo y métricas ---

import json

ENCABEZADO = "customer_id,name,age,country,email\n"


def test_mayoria_con_error_bloquea(capsys):
    assert vc.main([str(FIXTURES / "mayoria_con_error.csv")]) == 1
    salida = capsys.readouterr().out
    assert "::error" in salida
    assert "umbral de 50 %" in salida
    assert "@" not in salida


def test_limite_exacto_de_50_por_ciento_bloquea(tmp_path):
    ruta = tmp_path / "mitad.csv"
    ruta.write_text(ENCABEZADO + "C001,Ana,34,PE,ana@mail.com\nC002,,28,PE,luis@mail.com\n", encoding="utf-8")
    assert vc.validar(ruta, vc.PAISES_POR_DEFECTO).supera_umbral
    assert vc.main([str(ruta)]) == 1


def test_justo_debajo_del_umbral_solo_advierte(tmp_path):
    ruta = tmp_path / "casi.csv"
    filas = "C001,Ana,34,PE,a@mail.com\nC002,Luis,28,PE,l@mail.com\nC003,,41,CL,s@mail.com\n"
    ruta.write_text(ENCABEZADO + filas, encoding="utf-8")
    assert vc.main([str(ruta)]) == 0


def test_reporte_indica_el_umbral():
    reporte = vc.generar_reporte(vc.validar(vc.CSV_POR_DEFECTO, vc.PAISES_POR_DEFECTO))
    assert "se bloquea con 50 % o más" in reporte
    assert "Fase 1" not in reporte


def test_publica_las_metricas_del_stage(tmp_path, monkeypatch):
    salida = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salida))
    vc.main([])
    datos = json.loads(salida.read_text(encoding="utf-8").split("metricas=", 1)[1])
    assert datos["stage"] == "shift_left"
    assert datos["estado"] == "advertencia"
    assert (datos["filas_entrada"], datos["filas_salida"], datos["filas_rechazadas"]) == (21, 12, 9)
    assert "@" not in datos["mensaje"]


def test_metricas_de_fallo_estructural(tmp_path, monkeypatch):
    salida = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salida))
    vc.main([str(FIXTURES / "vacio.csv")])
    datos = json.loads(salida.read_text(encoding="utf-8").split("metricas=", 1)[1])
    assert datos["estado"] == "fallo"
