"""La configuración de Databricks falla con mensajes claros y nunca muestra secretos."""

import pytest

import db
import desplegar_modelo as dm

SECRETO = "dapi-valor-que-nunca-debe-aparecer"
COMPLETA = {
    "DATABRICKS_HOST": "https://dbc-ejemplo.cloud.databricks.com/",
    "DATABRICKS_HTTP_PATH": "/sql/1.0/warehouses/abc123",
    "DATABRICKS_TOKEN": SECRETO,
}


def test_sin_variables_nombra_las_tres():
    with pytest.raises(db.ConfiguracionInvalida) as error:
        db.leer_configuracion({})
    for variable in db.VARIABLES_REQUERIDAS:
        assert variable in str(error.value)


def test_falta_una_variable_y_no_muestra_valores():
    env = {**COMPLETA, "DATABRICKS_HOST": "  "}
    with pytest.raises(db.ConfiguracionInvalida) as error:
        db.leer_configuracion(env)
    mensaje = str(error.value)
    assert "DATABRICKS_HOST" in mensaje
    assert "DATABRICKS_TOKEN" not in mensaje
    assert SECRETO not in mensaje
    assert "abc123" not in mensaje


def test_configuracion_completa_limpia_el_host():
    config = db.leer_configuracion(COMPLETA)
    assert config.host == "dbc-ejemplo.cloud.databricks.com"
    assert config.token == SECRETO


def test_repr_de_la_configuracion_oculta_secretos():
    assert SECRETO not in repr(db.leer_configuracion(COMPLETA))


def test_destino_por_defecto():
    assert db.leer_destino({}) == ("workspace", "demo")


def test_destino_configurable():
    assert db.leer_destino({"DATABRICKS_CATALOG": "otro", "DATABRICKS_SCHEMA": "prod"}) == ("otro", "prod")


@pytest.mark.parametrize("valor", ["demo; DROP TABLE x", "demo.otro", "1demo", "de mo"])
def test_destino_rechaza_identificadores_peligrosos(valor):
    with pytest.raises(db.ConfiguracionInvalida):
        db.leer_destino({"DATABRICKS_SCHEMA": valor})


def test_run_id_en_github_actions():
    assert db.run_id({"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2"}) == "123-2"


def test_run_id_local():
    assert db.run_id({}).startswith("local-")


def test_despliegue_sin_secrets_falla_sin_conectarse(monkeypatch, capsys):
    for variable in db.VARIABLES_REQUERIDAS:
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(db, "conectar", lambda _: pytest.fail("no debe intentar conectarse"))
    assert dm.main() == 1
    salida = capsys.readouterr().out
    assert "::error" in salida
    assert "DATABRICKS_TOKEN" in salida
