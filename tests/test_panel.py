"""Prueba de humo del panel del personal (sin navegador, con AppTest de Streamlit)."""

from datetime import timedelta
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from reservas.disponibilidad import cargar_citas, obtener_bloqueos_del_dia  # noqa: E402
from reservas import config  # noqa: E402

PANEL = str(Path(__file__).resolve().parents[1] / "app" / "panel_empleadas.py")


def abrir_panel(monkeypatch, pin="1234"):
    monkeypatch.setenv("PANEL_PIN", pin)
    at = AppTest.from_file(PANEL, default_timeout=30)
    at.run()
    return at


def entrar(at, pin="1234"):
    at.text_input[0].input(pin)
    at.button[0].click().run()
    return at


def test_sin_pin_el_panel_no_se_abre(monkeypatch):
    monkeypatch.setenv("PANEL_PIN", "")
    at = AppTest.from_file(PANEL, default_timeout=30).run()
    assert at.error and "desactivado" in at.error[0].value
    assert not at.tabs


def test_pin_incorrecto_no_deja_pasar(monkeypatch):
    at = entrar(abrir_panel(monkeypatch), pin="0000")
    assert at.error and "incorrecto" in at.error[0].value
    assert not at.tabs


def test_el_panel_carga_con_el_pin_correcto(monkeypatch):
    at = entrar(abrir_panel(monkeypatch))
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Agenda del día", "Nueva cita", "Bloquear hueco"]


def test_apuntar_una_cita_por_telefono(monkeypatch):
    at = entrar(abrir_panel(monkeypatch))
    antes = len(cargar_citas())

    at.text_input(key="cita_tel_0").input("600 100 101").run()   # cliente existente
    assert at.success and "Laura" in at.success[0].value

    at.selectbox(key="cita_servicio_0").set_value(2)              # corte hombre, 30 min
    at.radio(key="cita_origen_0").set_value("telefono")
    at.run()
    at.button(key="cita_guardar_0").click().run()

    assert not at.exception, [e.value for e in at.exception]
    citas = cargar_citas()
    assert len(citas) == antes + 1
    assert citas.iloc[-1]["origen"] == "telefono"
    assert citas.iloc[-1]["id_cliente"] == 1


def test_cliente_nuevo_por_telefono_necesita_nombre(monkeypatch):
    at = entrar(abrir_panel(monkeypatch))
    at.text_input(key="cita_tel_0").input("699 000 111").run()
    at.button(key="cita_guardar_0").click().run()
    assert at.error and "nombre" in at.error[0].value

    at.text_input(key="cita_nombre_0").input("Rosa Gil").run()
    at.button(key="cita_guardar_0").click().run()
    assert not at.error
    assert cargar_citas().iloc[-1]["origen"] == "telefono"


def test_bloquear_un_dia_completo(monkeypatch):
    # Un día laborable dentro de un mes, para no chocar con citas de ejemplo.
    dia = config.ahora().date() + timedelta(days=30)
    while config.HORARIOS_NEGOCIO.get(dia.weekday()) is None:
        dia += timedelta(days=1)

    at = entrar(abrir_panel(monkeypatch))
    at.date_input(key="bloq_fecha_0").set_value(dia).run()
    at.checkbox(key="bloq_dia_0").check().run()
    at.button(key="bloq_guardar_0").click().run()

    assert not at.exception, [e.value for e in at.exception]
    assert not at.error
    bloqueos = obtener_bloqueos_del_dia(dia)
    assert len(bloqueos) == 1
    assert bloqueos.iloc[0]["hora_inicio"] == config.HORARIOS_NEGOCIO[dia.weekday()][0]
