"""Tests del stage 4 · Calidad de datos (scripts/calidad_datos.py), sin Databricks."""

import json

import calidad_datos as cd
import db
import validar_csv as vc
from conftest import ConexionFalsa, CursorFalso

PAISES = {"PE", "CL", "CO", "AR", "MX"}
FILAS_CSV, _ = vc.leer_filas(vc.CSV_POR_DEFECTO)
# El CSV real, como lo devolvería Bronze: crudo y con su número de fila.
BRONZE = [{"_row_number": i, **fila} for i, fila in enumerate(FILAS_CSV, start=1)]

SILVER_ESPERADO = [
    "C001", "C002", "C004", "C006", "C007", "C009", "C010", "C013", "C014", "C017", "C018", "C020",
]
RECHAZADOS_ESPERADOS = [
    (3, "C003", "nombre_vacio"),
    (5, "C005", "email_invalido"),
    (8, "C008", "nombre_vacio"),
    (11, "C010", "duplicado"),
    (12, "C011", "email_invalido"),
    (13, "C012", "edad_vacia"),
    (16, "C015", "edad_no_numerica"),
    (17, "C016", "pais_vacio"),
    (20, "C019", "email_vacio"),
]


def test_clasificar_csv_real_da_los_numeros_de_la_spec():
    c = cd.clasificar(BRONZE, PAISES)
    assert [f["customer_id"] for f in c.silver] == SILVER_ESPERADO
    assert c.contactables == 10
    assert c.menores == ["C004", "C009"]
    assert [(r["_row_number"], r["customer_id"], r["motivo"]) for r in c.rechazados] == RECHAZADOS_ESPERADOS
    assert round(c.pct_rechazo, 2) == 42.86
    assert not c.supera_umbral


def test_silver_queda_normalizada_y_con_banderas():
    filas = [{"_row_number": 1, "customer_id": " C001 ", "name": " Ana ", "age": " 17 ", "country": " pe ", "email": " a@b.co "}]
    (fila,) = cd.clasificar(filas, PAISES).silver
    assert fila == {
        "customer_id": "C001", "name": "Ana", "age": 17, "country_code": "PE", "email": "a@b.co",
        "es_mayor_edad": False, "es_contactable": False,
    }


def test_registro_original_es_el_dato_crudo_en_json():
    c = cd.clasificar(BRONZE, PAISES)
    por_id = {r["customer_id"]: json.loads(r["registro_original"]) for r in c.rechazados}
    assert por_id["C008"]["name"] == "  "
    assert por_id["C015"]["age"] == "abc"
    assert set(por_id["C003"]) == {"customer_id", "name", "age", "country", "email"}
    assert "Andrés" in next(r["registro_original"] for r in c.rechazados if r["customer_id"] == "C012")


def test_customer_id_vacio_se_guarda_como_nulo():
    filas = [{"_row_number": 1, "customer_id": "  ", "name": "Ana", "age": "30", "country": "PE", "email": "a@b.co"}]
    (rechazado,) = cd.clasificar(filas, PAISES).rechazados
    assert rechazado["customer_id"] is None


def test_escribir_bajo_el_umbral_reemplaza_silver_y_guarda_rechazados():
    cursor = CursorFalso()
    cd.escribir(cursor, cd.clasificar(BRONZE, PAISES), "9-1", "workspace", "demo")
    sentencias = cursor.sentencias()
    assert sentencias[0].startswith("DELETE FROM workspace.demo.rechazados_customers WHERE _run_id = :run_id")
    assert sentencias[1].startswith("INSERT INTO workspace.demo.rechazados_customers")
    assert sentencias[2].startswith("INSERT OVERWRITE workspace.demo.silver_customers")
    assert len(sentencias) == 3
    parametros_silver = cursor.ejecutadas[2][1]
    assert parametros_silver["customer_id_0"] == "C001" and parametros_silver["run_id"] == "9-1"


def test_escribir_en_lotes_solo_el_primero_reemplaza(monkeypatch):
    monkeypatch.setattr(cd, "TAMANO_LOTE", 5)
    cursor = CursorFalso()
    cd.escribir(cursor, cd.clasificar(BRONZE, PAISES), "9-1", "workspace", "demo")
    silver = [s for s in cursor.sentencias() if "silver_customers" in s]
    assert silver[0].startswith("INSERT OVERWRITE")
    assert all(s.startswith("INSERT INTO") for s in silver[1:])
    assert len(silver) == 3  # 12 filas en lotes de 5


def test_con_umbral_superado_guarda_rechazados_y_no_toca_silver():
    malas = [{"_row_number": i, "customer_id": f"X{i}", "name": "", "age": "30", "country": "PE", "email": "a@b.co"} for i in range(1, 4)]
    buena = [{"_row_number": 4, "customer_id": "X4", "name": "Ana", "age": "30", "country": "PE", "email": "a@b.co"}]
    c = cd.clasificar(malas + buena, PAISES)
    assert c.supera_umbral
    cursor = CursorFalso()
    cd.escribir(cursor, c, "9-1", "workspace", "demo")
    assert any(s.startswith("INSERT INTO workspace.demo.rechazados_customers") for s in cursor.sentencias())
    assert not any("silver_customers" in s for s in cursor.sentencias())


def test_resumen_no_muestra_emails():
    resumen = cd.generar_resumen(cd.clasificar(BRONZE, PAISES))
    assert "@" not in resumen
    assert "| 11 | C010 | duplicado |" in resumen


def correr_main(monkeypatch, tmp_path, bronze):
    filas = [tuple(f[col] for col in ("_row_number", "customer_id", "name", "age", "country", "email")) for f in bronze]
    cursor = CursorFalso(resultados=[filas, [(p,) for p in sorted(PAISES)]])
    monkeypatch.setattr(db, "conectar", lambda _: ConexionFalsa(cursor))
    monkeypatch.setenv("RUN_ID", "777-1")
    salida = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salida))
    codigo = cd.main()
    datos = json.loads(salida.read_text(encoding="utf-8").split("metricas=", 1)[1])
    return codigo, datos, cursor


def test_main_advierte_con_el_csv_real(monkeypatch, tmp_path, capsys, secrets_falsos):
    codigo, datos, cursor = correr_main(monkeypatch, tmp_path, BRONZE)
    assert codigo == 0
    assert (datos["estado"], datos["filas_entrada"], datos["filas_salida"], datos["filas_rechazadas"]) == ("advertencia", 21, 12, 9)
    assert cursor.ejecutadas[0][1] == {"run_id": "777-1"}  # usa el run_id del stage 3
    salida = capsys.readouterr().out
    assert "::warning" in salida and "@" not in salida


def test_main_exito_sin_rechazos(monkeypatch, tmp_path, secrets_falsos):
    codigo, datos, _ = correr_main(monkeypatch, tmp_path, BRONZE[:2])
    assert (codigo, datos["estado"]) == (0, "exito")


def test_main_falla_con_umbral_superado(monkeypatch, tmp_path, capsys, secrets_falsos):
    codigo, datos, _ = correr_main(monkeypatch, tmp_path, BRONZE[2:4])  # C003 (error) y C004 (válido)
    assert codigo == 1
    assert datos["estado"] == "fallo" and datos["filas_salida"] == 0
    assert "::error" in capsys.readouterr().out


def test_main_falla_si_bronze_esta_vacio(monkeypatch, tmp_path, secrets_falsos):
    codigo, datos, _ = correr_main(monkeypatch, tmp_path, [])
    assert (codigo, datos["estado"]) == (1, "fallo")
