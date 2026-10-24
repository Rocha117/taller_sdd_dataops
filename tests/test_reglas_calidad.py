"""Tests de las reglas de calidad por fila (scripts/reglas_calidad.py)."""

import pytest

import reglas_calidad as rc

PAISES = {"PE", "CL", "CO", "AR", "MX"}
VALIDA = {"customer_id": "C001", "name": "Ana Torres", "age": "34", "country": "PE", "email": "ana@mail.com"}


def evaluar_una(**cambios):
    return rc.evaluar_filas([{**VALIDA, **cambios}], PAISES)[0]


def test_fila_valida_no_tiene_motivos():
    resultado = evaluar_una()
    assert resultado.es_valida
    assert resultado.motivos == ()
    assert not resultado.es_menor_de_edad


@pytest.mark.parametrize(
    "cambios, motivo",
    [
        ({"customer_id": ""}, rc.CUSTOMER_ID_VACIO),
        ({"name": ""}, rc.NOMBRE_VACIO),
        ({"name": "   "}, rc.NOMBRE_VACIO),
        ({"age": ""}, rc.EDAD_VACIA),
        ({"age": "abc"}, rc.EDAD_NO_NUMERICA),
        ({"age": "34.5"}, rc.EDAD_NO_NUMERICA),
        ({"age": "121"}, rc.EDAD_FUERA_DE_RANGO),
        ({"age": "-1"}, rc.EDAD_FUERA_DE_RANGO),
        ({"country": ""}, rc.PAIS_VACIO),
        ({"country": "BR"}, rc.PAIS_DESCONOCIDO),
        ({"email": ""}, rc.EMAIL_VACIO),
        ({"email": "sin.arroba.com"}, rc.EMAIL_INVALIDO),
        ({"email": "jorge.salas@mail"}, rc.EMAIL_INVALIDO),
        ({"email": "con espacio@mail.com"}, rc.EMAIL_INVALIDO),
    ],
)
def test_cada_regla_produce_su_motivo(cambios, motivo):
    assert evaluar_una(**cambios).motivos == (motivo,)


@pytest.mark.parametrize("edad", ["0", "18", "120"])
def test_limites_de_edad_validos(edad):
    assert evaluar_una(age=edad).es_valida


def test_varios_motivos_en_orden_y_separados():
    resultado = evaluar_una(name="", age="abc", email="")
    assert resultado.motivos == (rc.NOMBRE_VACIO, rc.EDAD_NO_NUMERICA, rc.EMAIL_VACIO)
    assert resultado.motivo == "nombre_vacio; edad_no_numerica; email_vacio"


def test_duplicado_manda_la_primera_fila():
    resultados = rc.evaluar_filas([VALIDA, VALIDA, VALIDA], PAISES)
    assert resultados[0].es_valida
    assert resultados[1].motivos == (rc.DUPLICADO,)
    assert resultados[2].motivos == (rc.DUPLICADO,)


def test_duplicado_manda_la_primera_aunque_tenga_errores():
    primera = {**VALIDA, "email": ""}
    resultados = rc.evaluar_filas([primera, VALIDA], PAISES)
    assert resultados[0].motivos == (rc.EMAIL_VACIO,)
    assert resultados[1].motivos == (rc.DUPLICADO,)


def test_customer_id_vacio_repetido_no_es_duplicado():
    sin_id = {**VALIDA, "customer_id": ""}
    resultados = rc.evaluar_filas([sin_id, sin_id], PAISES)
    assert all(r.motivos == (rc.CUSTOMER_ID_VACIO,) for r in resultados)


def test_duplicado_se_detecta_despues_de_normalizar():
    resultados = rc.evaluar_filas([VALIDA, {**VALIDA, "customer_id": " C001 "}], PAISES)
    assert resultados[1].motivos == (rc.DUPLICADO,)


def test_menor_de_edad_valido_es_informacion_no_error():
    resultado = evaluar_una(age="17")
    assert resultado.es_valida
    assert resultado.es_menor_de_edad


def test_menor_con_errores_no_se_cuenta_como_menor():
    resultado = evaluar_una(age="16", email="")
    assert not resultado.es_valida
    assert not resultado.es_menor_de_edad


def test_normalizacion_quita_espacios_y_pasa_pais_a_mayusculas():
    fila = rc.normalizar({"customer_id": " C001 ", "name": " Ana ", "age": " 34 ", "country": " pe ", "email": " a@b.co "})
    assert fila == {"customer_id": "C001", "name": "Ana", "age": "34", "country": "PE", "email": "a@b.co"}
    assert evaluar_una(country=" pe ", age=" 34 ").es_valida


def test_normalizacion_tolera_valores_nulos():
    assert rc.normalizar({"customer_id": None})["name"] == ""


def test_numeracion_empieza_en_uno():
    resultados = rc.evaluar_filas([VALIDA, {**VALIDA, "customer_id": "C002"}], PAISES)
    assert [r.numero for r in resultados] == [1, 2]


def test_resultado_no_guarda_el_email():
    resultado = evaluar_una()
    assert "@" not in repr(resultado)
