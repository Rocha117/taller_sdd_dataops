"""Tests del stage 6 · Monitoreo (scripts/registrar_monitoreo.py), sin Databricks."""

import json

import pytest

import db
import registrar_monitoreo as rm
from conftest import ConexionFalsa, CursorFalso

AHORA = "2026-10-26T11:00:00Z"


def job(resultado, **metricas):
    salida = {"metricas": json.dumps(metricas)} if metricas else {}
    return {"result": resultado, "outputs": salida}


def m(stage, estado="exito", **extra):
    return {"stage": stage, "estado": estado, "mensaje": "ok", "started_at": "2026-10-26T11:00:01Z",
            "finished_at": "2026-10-26T11:00:09Z", **extra}


NEEDS_VERDE = {
    "calidad-shift-left": job("success", **m("shift_left", "advertencia", filas_entrada=21, filas_salida=12, filas_rechazadas=9)),
    "despliegue-modelo": job("success", **m("despliegue_modelo", filas_salida=5)),
    "ingesta-bronze": {**job("success", **m("bronze", filas_entrada=21, filas_salida=21)),
                       "outputs": {"metricas": json.dumps(m("bronze", filas_entrada=21, filas_salida=21)), "run_id": "100-1"}},
    "calidad-datos": job("success", **m("calidad", "advertencia", filas_entrada=21, filas_salida=12, filas_rechazadas=9)),
    "gold": job("success", **m("gold", filas_entrada=12, filas_salida=6)),
}


def por_stage(filas):
    return {f["stage"]: f for f in filas}


def test_todo_en_verde_arma_seis_filas():
    filas, con_fallo = rm.armar_filas(NEEDS_VERDE, "100-1", "pull_request", "abc123", AHORA)
    assert con_fallo == []
    assert [f["stage"] for f in filas] == ["shift_left", "despliegue_modelo", "bronze", "calidad", "gold", "monitoreo"]
    s = por_stage(filas)
    assert (s["shift_left"]["estado"], s["calidad"]["estado"]) == ("advertencia", "advertencia")
    assert (s["calidad"]["filas_entrada"], s["calidad"]["filas_salida"], s["calidad"]["filas_rechazadas"]) == (21, 12, 9)
    assert (s["monitoreo"]["estado"], s["monitoreo"]["filas_entrada"], s["monitoreo"]["filas_salida"], s["monitoreo"]["filas_rechazadas"]) == ("exito", 5, 6, 0)
    assert all(f["run_id"] == "100-1" and f["git_sha"] == "abc123" and f["trigger"] == "pull_request" for f in filas)


def test_si_falla_el_shift_left_los_demas_quedan_como_no_corrieron():
    needs = {"calidad-shift-left": job("failure", **m("shift_left", "fallo", mensaje="encabezado distinto"))}
    needs.update({j: {"result": "skipped", "outputs": {}} for j in ("despliegue-modelo", "ingesta-bronze", "calidad-datos", "gold")})
    filas, con_fallo = rm.armar_filas(needs, "200-1", "pull_request", "abc", AHORA)
    s = por_stage(filas)
    assert con_fallo == ["shift_left", "despliegue_modelo", "bronze", "calidad", "gold"]
    assert s["shift_left"]["estado"] == "fallo" and s["shift_left"]["mensaje"] == "encabezado distinto"
    for stage in ("despliegue_modelo", "bronze", "calidad", "gold"):
        assert s[stage]["estado"] == "fallo"
        assert s[stage]["mensaje"] == "No corrió: falló un stage anterior"
        assert s[stage]["started_at"] == AHORA and s[stage]["filas_entrada"] is None
    assert s["monitoreo"]["estado"] == "fallo"
    assert len(filas) == 6


def test_job_fallido_sin_metricas():
    needs = {**NEEDS_VERDE, "gold": {"result": "failure", "outputs": {}}}
    filas, con_fallo = rm.armar_filas(needs, "1-1", "schedule", "x", AHORA)
    assert con_fallo == ["gold"]
    assert por_stage(filas)["gold"]["mensaje"] == "El job terminó en failure sin publicar métricas"


def test_job_cancelado_es_fallo():
    needs = {**NEEDS_VERDE, "calidad-datos": job("cancelled", **m("calidad"))}
    _, con_fallo = rm.armar_filas(needs, "1-1", "schedule", "x", AHORA)
    assert con_fallo == ["calidad"]


@pytest.mark.parametrize("evento, esperado", [("pull_request", "pull_request"), ("schedule", "schedule"), ("workflow_dispatch", "manual")])
def test_traduccion_de_trigger(evento, esperado):
    filas, _ = rm.armar_filas(NEEDS_VERDE, "1-1", evento, "x", AHORA)
    assert {f["trigger"] for f in filas} == {esperado}


def test_run_id_del_stage_3_tiene_prioridad(monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "100")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    assert rm.run_id_de_la_ejecucion(NEEDS_VERDE) == "100-1"
    assert rm.run_id_de_la_ejecucion({}) == "100-2"


def test_mensajes_nunca_muestran_emails():
    needs = {**NEEDS_VERDE, "gold": job("failure", **m("gold", "fallo", mensaje="error con ana.torres@mail.com"))}
    filas, _ = rm.armar_filas(needs, "1-1", "schedule", "x", AHORA)
    assert all("@" not in f["mensaje"] for f in filas)
    assert "@" not in rm.generar_resumen(filas)


def test_escribir_borra_inserta_y_cuenta():
    filas, _ = rm.armar_filas(NEEDS_VERDE, "100-1", "pull_request", "abc", AHORA)
    cursor = CursorFalso(resultados=[[(6,)]])
    assert rm.escribir(cursor, filas, "workspace", "demo") == 6
    sentencias = cursor.sentencias()
    assert sentencias[0].startswith("DELETE FROM workspace.demo.monitoreo_ejecuciones WHERE run_id = :run_id")
    assert sentencias[1].startswith("INSERT INTO workspace.demo.monitoreo_ejecuciones")
    assert "`trigger`" in sentencias[1]
    parametros = cursor.ejecutadas[1][1]
    assert parametros["stage_5"] == "monitoreo" and parametros["filas_rechazadas_0"] == 9


def correr_main(monkeypatch, needs, conteo=6):
    cursor = CursorFalso(resultados=[[(conteo,)]])
    monkeypatch.setattr(db, "conectar", lambda _: ConexionFalsa(cursor))
    monkeypatch.setenv("NEEDS_JSON", json.dumps(needs))
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_SHA", "abc")
    return rm.main()


def test_main_en_verde(monkeypatch, secrets_falsos):
    assert correr_main(monkeypatch, NEEDS_VERDE) == 0


def test_main_termina_en_rojo_si_algun_stage_fallo(monkeypatch, capsys, secrets_falsos):
    needs = {**NEEDS_VERDE, "gold": {"result": "failure", "outputs": {}}}
    assert correr_main(monkeypatch, needs) == 1
    assert "::error title=Monitoreo::Stages que no terminaron en verde: gold" in capsys.readouterr().out


def test_main_falla_si_no_quedan_seis_filas(monkeypatch, secrets_falsos):
    assert correr_main(monkeypatch, NEEDS_VERDE, conteo=5) == 1
