"""El contrato del modelo, los DDL y el despliegue no se pueden contradecir."""

import re

import pytest

import db
import desplegar_modelo as dm

_TABLA = re.compile(r"CREATE TABLE IF NOT EXISTS \{\{catalog\}\}\.\{\{schema\}\}\.(\w+)\s*\(")
_COLUMNA = re.compile(r"^\s*`?(\w+)`?\s+(STRING|INT|BIGINT|BOOLEAN|TIMESTAMP|DECIMAL\(\d+,\d+\))(?=\s|$)(.*)$")


def columnas_de_ddl(texto):
    """Extrae {columna: (tipo, resto_de_la_linea)} de un CREATE TABLE."""
    cuerpo = texto[texto.index("(") + 1 : texto.rindex(")")]
    columnas = {}
    for linea in cuerpo.splitlines():
        coincidencia = _COLUMNA.match(linea)
        if coincidencia:
            columnas[coincidencia.group(1)] = (coincidencia.group(2), coincidencia.group(3))
    return columnas


DDL = {
    _TABLA.search(ruta.read_text(encoding="utf-8")).group(1): ruta.read_text(encoding="utf-8")
    for ruta in dm.archivos_ddl()
}
CONTRATO = dm.leer_contrato()


def test_hay_seis_ddl_en_orden():
    nombres = [r.name for r in dm.archivos_ddl()]
    assert nombres == [
        "01_bronze_customers.sql",
        "02_silver_customers.sql",
        "03_rechazados_customers.sql",
        "04_ref_paises.sql",
        "05_gold_contactables_pais.sql",
        "06_monitoreo_ejecuciones.sql",
    ]


def test_contrato_y_ddl_tienen_las_mismas_tablas():
    assert set(DDL) == set(CONTRATO)


@pytest.mark.parametrize("tabla", sorted(CONTRATO))
def test_contrato_y_ddl_tienen_las_mismas_columnas_y_tipos(tabla):
    ddl = {col: tipo for col, (tipo, _) in columnas_de_ddl(DDL[tabla]).items()}
    assert ddl == CONTRATO[tabla]


@pytest.mark.parametrize("tabla", sorted(CONTRATO))
def test_ddl_cumple_las_reglas_comunes(tabla):
    texto = DDL[tabla]
    assert "CREATE TABLE IF NOT EXISTS {{catalog}}.{{schema}}." in texto
    assert "DROP" not in texto.upper()
    assert "USING DELTA" in texto
    assert re.search(r"\)\s*USING DELTA\s*COMMENT '", texto), "falta el comentario de la tabla"
    sin_comentario = [c for c, (_, resto) in columnas_de_ddl(texto).items() if "COMMENT '" not in resto]
    assert sin_comentario == []


def test_columnas_con_pii_estan_marcadas():
    pii = {
        ("bronze_customers", "email"),
        ("silver_customers", "email"),
        ("rechazados_customers", "registro_original"),
    }
    for tabla, columna in pii:
        assert "PII" in columnas_de_ddl(DDL[tabla])[columna][1]


def test_gold_no_tiene_emails():
    assert not [c for c in CONTRATO["gold_contactables_pais"] if "email" in c.lower()]


def test_cada_ddl_tiene_una_sola_sentencia():
    for ruta in dm.archivos_ddl():
        sentencia = dm.preparar_sentencia(ruta.read_text(encoding="utf-8"))
        assert not sentencia.endswith(";")
        assert sentencia.count("CREATE TABLE") == 1


def test_renderizar_reemplaza_catalogo_y_schema():
    texto = db.renderizar_sql(DDL["ref_paises"], "workspace", "demo")
    assert "workspace.demo.ref_paises" in texto
    assert "{{" not in texto


def test_paises_de_referencia():
    assert dm.leer_paises() == [
        {"country_code": "PE", "country_name": "Perú", "region": "Sudamérica"},
        {"country_code": "CL", "country_name": "Chile", "region": "Sudamérica"},
        {"country_code": "CO", "country_name": "Colombia", "region": "Sudamérica"},
        {"country_code": "AR", "country_name": "Argentina", "region": "Sudamérica"},
        {"country_code": "MX", "country_name": "México", "region": "Norteamérica"},
    ]


def test_merge_de_paises_es_parametrizado():
    assert ":country_code" in dm.SQL_MERGE_PAIS
    assert "MERGE INTO {{catalog}}.{{schema}}.ref_paises" in dm.SQL_MERGE_PAIS


def test_comparar_contrato_sin_diferencias():
    real = {t: {c: tipo.lower() for c, tipo in cols.items()} for t, cols in CONTRATO.items()}
    assert dm.comparar_contrato(CONTRATO, real) == ([], [])


def test_comparar_contrato_detecta_tabla_columna_y_tipo():
    real = {t: dict(cols) for t, cols in CONTRATO.items() if t != "ref_paises"}
    del real["silver_customers"]["email"]
    real["gold_contactables_pais"]["pct_contactables"] = "decimal(10,2)"
    errores, _ = dm.comparar_contrato(CONTRATO, real)
    assert "Falta la tabla ref_paises." in errores
    assert "Falta la columna silver_customers.email." in errores
    assert any("gold_contactables_pais.pct_contactables" in e for e in errores)


def test_comparar_contrato_columnas_extra_solo_advierten():
    real = {t: dict(cols) for t, cols in CONTRATO.items()}
    real["ref_paises"]["nueva"] = "STRING"
    assert dm.comparar_contrato(CONTRATO, real) == ([], ["ref_paises.nueva"])
