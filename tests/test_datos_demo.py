"""Tests del generador de datos de demostración y del panel de la propietaria."""

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

import analitica as an
import generar_datos_demo as gen
from reservas import config, db
from reservas.disponibilidad import cargar_citas

HOY = date(2026, 9, 29)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(config, "ahora", lambda: datetime(2026, 9, 29, 10, 0))


def generar(**kwargs):
    return gen.generar(meses=3, n_clientes=90, hoy=HOY, **kwargs)


def test_cada_venta_tiene_su_cita_y_no_hay_solapes():
    resumen = generar()
    ventas = pd.read_csv(config.DATA_DIR / "ventas.csv")
    citas = cargar_citas()

    generadas = citas[(citas["id_cita"] >= gen.PRIMER_ID_CITA_DEMO) & (citas["estado"] == "confirmada")]
    assert len(ventas) == len(generadas) == resumen["ventas"] > 100

    # Ninguna profesional tiene dos citas confirmadas a la vez.
    confirmadas = citas[citas["estado"] == "confirmada"].copy()
    confirmadas["ini"] = confirmadas["hora_inicio"].map(gen.hora_a_minutos)
    confirmadas["fin"] = confirmadas["hora_fin"].map(gen.hora_a_minutos)
    for (_, _), grupo in confirmadas.groupby(["fecha", "id_empleado"]):
        grupo = grupo.sort_values("ini")
        assert (grupo["ini"].iloc[1:].values >= grupo["fin"].iloc[:-1].values).all()


def test_las_ventas_son_coherentes_con_el_catalogo():
    generar()
    ventas = pd.read_csv(config.DATA_DIR / "ventas.csv")
    servicios = pd.read_csv(config.DATA_DIR / "servicios.csv")
    empleados = pd.read_csv(config.DATA_DIR / "empleados.csv", encoding="utf-8-sig")

    assert set(ventas["servicio"]) <= set(servicios["nombre"])
    assert set(ventas["empleado"]) <= set(empleados["nombre"])
    assert (pd.to_datetime(ventas["fecha"]).dt.date < HOY).all()
    # el importe es el precio del catálogo
    precios = dict(zip(servicios["nombre"], servicios["precio"]))
    assert all(precios[s] == i for s, i in zip(ventas["servicio"], ventas["importe"]))


def test_los_clientes_de_demo_tienen_telefonos_que_no_existen():
    generar()
    clientes = db.leer("SELECT * FROM clientes")
    demo = clientes[clientes["telefono"].str.startswith(gen.PREFIJO_TELEFONO_DEMO)]
    assert len(demo) > 50
    assert not any(len(t) == 9 and t[0] in "67" for t in demo["telefono"])


def test_se_puede_repetir_sin_duplicar_clientes_ni_citas():
    primera = generar()
    clientes_1 = len(db.leer("SELECT * FROM clientes"))
    citas_1 = len(cargar_citas())

    segunda = generar()

    assert len(db.leer("SELECT * FROM clientes")) == clientes_1
    assert len(cargar_citas()) == citas_1                       # misma semilla, mismo historial
    assert segunda["ventas"] == primera["ventas"]


def test_no_toca_las_citas_futuras_ni_los_bloqueos():
    db.leer("SELECT 1")                                         # crea la BD a partir de los CSV
    futuras_antes = cargar_citas().query("fecha >= '2026-09-29'")
    generar()
    futuras_despues = cargar_citas().query("fecha >= '2026-09-29'")
    assert len(futuras_despues) == len(futuras_antes)


def test_crea_copia_de_seguridad():
    resumen = generar()
    copia = Path(resumen["copia_de_seguridad"])
    assert (copia / "studio_alba.db").exists()
    assert (copia / "ventas.csv").exists()


def test_los_datos_generados_dan_estadisticas_razonables():
    generar()
    datos = an.cargar_datos()
    desde = pd.Timestamp(HOY) - pd.DateOffset(months=3)
    k = an.kpis(datos, desde, pd.Timestamp(HOY))
    assert k["ingresos"] > 5000 and k["servicios"] > 100
    assert 0 < an.ocupacion(datos, desde, pd.Timestamp(HOY), pd.Timestamp(HOY))["ocupacion"].max() < 1
    assert len(an.lista_reactivacion(an.resumen_clientes(datos, pd.Timestamp(HOY)))) > 0


# ---------------- panel de la propietaria (Streamlit AppTest) ----------------

from streamlit.testing.v1 import AppTest  # noqa: E402

PANEL = str(Path(__file__).resolve().parents[1] / "app" / "panel_propietaria.py")


def abrir_panel(monkeypatch, pin="4321"):
    monkeypatch.setenv("OWNER_PIN", pin)
    at = AppTest.from_file(PANEL, default_timeout=60)
    at.run()
    return at


def entrar(at, pin="4321"):
    at.text_input[0].input(pin)
    at.button[0].click().run()
    return at


def test_panel_sin_pin_no_se_abre(monkeypatch):
    monkeypatch.setenv("OWNER_PIN", "")
    at = AppTest.from_file(PANEL, default_timeout=30).run()
    assert at.error and "desactivado" in at.error[0].value


SECCIONES = ["Resumen", "Ingresos", "Costes", "Clientes", "Agenda", "Marketing"]


def recorrer_secciones(at):
    for seccion in SECCIONES:
        at.radio(key="seccion").set_value(seccion).run()
        assert not at.exception, (seccion, [e.value for e in at.exception])


def test_panel_pin_incorrecto(monkeypatch):
    at = entrar(abrir_panel(monkeypatch), pin="0000")
    assert at.error and "incorrecto" in at.error[0].value
    assert not at.radio                                   # el menú solo aparece tras entrar


def test_panel_con_datos_de_demo_carga_todas_las_secciones(monkeypatch):
    generar()
    at = entrar(abrir_panel(monkeypatch))

    assert not at.exception, [e.value for e in at.exception]
    assert at.radio(key="seccion").options == SECCIONES
    recorrer_secciones(at)


def test_panel_funciona_con_todos_los_periodos_en_todas_las_secciones(monkeypatch):
    generar()
    at = entrar(abrir_panel(monkeypatch))

    for periodo in ["Este mes", "Mes anterior", "Últimos 6 meses", "Todo el historial"]:
        at.radio(key="periodo").set_value(periodo).run()
        assert not at.exception, (periodo, [e.value for e in at.exception])
        recorrer_secciones(at)


def test_panel_con_los_datos_originales_pocos_datos(monkeypatch):
    """Sin generar datos de demo (un solo mes de ventas) el panel tiene que abrir igual."""
    at = entrar(abrir_panel(monkeypatch))
    recorrer_secciones(at)


def test_panel_sin_ventas_no_falla(monkeypatch, datos_temporales):
    pd.DataFrame(columns=["id_venta", "fecha", "id_cliente", "servicio", "empleado", "importe"]).to_csv(
        datos_temporales / "ventas.csv", index=False)
    at = entrar(abrir_panel(monkeypatch))
    recorrer_secciones(at)


def test_cerrar_sesion_vuelve_al_pin(monkeypatch):
    at = entrar(abrir_panel(monkeypatch))
    at.button(key="salir").click().run()
    assert not at.radio and at.text_input


def test_el_nombre_de_un_cliente_no_puede_inyectar_html(monkeypatch):
    from reservas.clientes import buscar_o_crear_cliente
    buscar_o_crear_cliente("<script>alert(1)</script> Ana", "611222333")
    at = entrar(abrir_panel(monkeypatch))
    recorrer_secciones(at)
    cuerpo = " ".join(m.value for m in at.markdown)
    assert "<script>" not in cuerpo


def test_los_enlaces_de_whatsapp_usan_el_mensaje_y_no_envian_a_numeros_falsos(monkeypatch):
    generar()
    at = entrar(abrir_panel(monkeypatch))
    at.radio(key="seccion").set_value("Marketing").run()
    at.text_area(key="plantilla_mensaje").set_value("Hola {nombre}, te echamos de menos.").run()
    assert not at.exception, [e.value for e in at.exception]

    tabla = [df for df in at.dataframe if "whatsapp" in df.value.columns]
    assert tabla
    filas = tabla[0].value
    assert len(filas) > 0
    assert all(e.startswith("https://wa.me/") and "Hola" in e for e in filas["whatsapp"])

    for telefono, enlace in zip(filas["telefono"], filas["whatsapp"]):
        if str(telefono).startswith(gen.PREFIJO_TELEFONO_DEMO):
            # Teléfono de demo: el enlace no lleva número, se elige el contacto en WhatsApp.
            assert enlace.startswith("https://wa.me/?text=")
        else:
            assert enlace.startswith(f"https://wa.me/34{telefono}?text=")
