"""Tests de scripts/metricas.py."""

import json

import pytest

import metricas
import reglas_calidad as rc


def leer_salida(ruta):
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    return dict(linea.split("=", 1) for linea in lineas)


def test_publica_json_con_todas_las_claves(tmp_path, monkeypatch):
    salida = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salida))
    with metricas.registrar("bronze") as m:
        m.filas_entrada = 21
        m.filas_salida = 21
    datos = json.loads(leer_salida(salida)["metricas"])
    assert datos["stage"] == "bronze"
    assert datos["estado"] == "exito"
    assert set(datos) == {
        "stage", "estado", "filas_entrada", "filas_salida", "filas_rechazadas",
        "mensaje", "started_at", "finished_at",
    }
    assert datos["started_at"].endswith("Z") and datos["finished_at"].endswith("Z")


def test_publica_aunque_haya_una_excepcion(tmp_path, monkeypatch):
    salida = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salida))
    with pytest.raises(RuntimeError):
        with metricas.registrar("gold"):
            raise RuntimeError("se cayó")
    datos = json.loads(leer_salida(salida)["metricas"])
    assert datos["estado"] == "fallo"
    assert "se cayó" in datos["mensaje"]


def test_sin_github_output_no_falla(capsys):
    with metricas.registrar("calidad") as m:
        m.advertir("9 filas rechazadas")
    assert '"estado": "advertencia"' in capsys.readouterr().out


def test_advertir_no_pisa_un_fallo():
    m = metricas.Metricas("calidad")
    m.fallar("umbral superado")
    m.advertir("otra cosa")
    assert m.estado == "fallo"
    assert m.mensaje == "umbral superado"


def test_publicar_otra_salida(tmp_path, monkeypatch):
    salida = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salida))
    metricas.publicar_salida("run_id", "123-1")
    assert leer_salida(salida) == {"run_id": "123-1"}


@pytest.mark.parametrize(
    "texto",
    ["falló con ana.torres@mail.com", "valor 'jorge.salas@mail' inválido", "solo una @ suelta"],
)
def test_sin_emails_oculta_cualquier_email(texto):
    assert "@" not in metricas.sin_emails(texto)


def test_mensajes_de_metricas_no_muestran_emails():
    m = metricas.Metricas("bronze")
    m.fallar("error en ana.torres@mail.com")
    assert "@" not in m.como_json()


@pytest.mark.parametrize(
    "rechazadas, total, esperado",
    [(0, 21, False), (9, 21, False), (10, 21, False), (11, 21, True), (1, 2, True), (2, 4, True), (0, 0, False)],
)
def test_umbral_de_rechazo(rechazadas, total, esperado):
    assert rc.supera_umbral(rechazadas, total) is esperado
