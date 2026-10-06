"""Tests de las estadísticas del panel de la propietaria, con datos pequeños hechos a mano."""

import pandas as pd
import pytest

import analitica as an

HOY = pd.Timestamp("2026-09-29")


def d(texto):
    return pd.Timestamp(texto)


@pytest.fixture
def datos():
    ventas = pd.DataFrame([
        # cliente 1: recurrente (3 visitas)
        (1, d("2026-06-01"), 1, "Corte mujer", "Alba", 25),
        (2, d("2026-07-01"), 1, "Tinte", "Marta", 55),
        (3, d("2026-09-20"), 1, "Corte mujer", "Alba", 25),
        # cliente 2: nueva (1 visita reciente)
        (4, d("2026-09-25"), 2, "Balayage", "Marta", 120),
        # cliente 3: perdida (última visita hace más de 120 días)
        (5, d("2026-03-01"), 3, "Corte hombre", "Alba", 18),
        (6, d("2026-04-01"), 3, "Corte hombre", "Alba", 18),
        # cliente 4: en riesgo (76 días)
        (7, d("2026-07-15"), 4, "Mechas", "Marta", 90),
    ], columns=["id_venta", "fecha", "id_cliente", "servicio", "empleado", "importe"])

    clientes = pd.DataFrame({
        "id_cliente": [1, 2, 3, 4, 5],
        "nombre": ["Ana Ruiz", "Bea Gil", "Carla Sanz", "Dora Pons", "Eva Mora"],
        "telefono": ["600000001", "600000002", "600000003", "600000004", "600000005"],
        "fecha_alta": [d("2026-01-10"), d("2026-09-01"), d("2026-02-01"), d("2026-05-01"), d("2026-09-10")],
    })

    citas = pd.DataFrame([
        (1, 1, 1, 1, d("2026-09-28"), "09:30", "10:30", "confirmada", "telefono"),
        (2, 2, 1, 2, d("2026-09-28"), "10:00", "11:00", "cancelada", "asistente"),
        (3, 2, 1, 1, d("2026-09-28"), "11:00", "12:00", "confirmada", "asistente"),
    ], columns=["id_cita", "id_cliente", "id_servicio", "id_empleado", "fecha", "hora_inicio", "hora_fin", "estado", "origen"])

    gastos = pd.DataFrame([
        (1, d("2026-09-02"), "Alquiler", "Local", 850),
        (2, d("2026-09-06"), "Marketing", "Instagram", 100),
    ], columns=["id_gasto", "fecha", "categoria", "concepto", "importe"])

    compras = pd.DataFrame([(1, d("2026-09-05"), "Beauty Pro", "Tinte", 10, 70)],
                           columns=["id_compra", "fecha", "proveedor", "producto", "cantidad", "importe"])

    empleados = pd.DataFrame({"id_empleado": [1, 2], "nombre": ["Alba", "Marta"], "pago_mes": [1000, 500]})

    servicios = pd.DataFrame({
        "id_servicio": [1, 2], "nombre": ["Corte mujer", "Balayage"],
        "precio": [25, 120], "duracion_minutos": [45, 210],
    })

    return {"ventas": ventas, "gastos": gastos, "compras": compras, "empleados": empleados,
            "servicios": servicios, "clientes": clientes, "citas": citas}


# ---------------- dinero ----------------

def test_nominas_se_reparten_por_dias():
    empleados = pd.DataFrame({"pago_mes": [1000, 500]})
    assert an.nominas(empleados, "2026-09-01", "2026-09-30") == pytest.approx(1500)
    assert an.nominas(empleados, "2026-09-01", "2026-09-15") == pytest.approx(750)
    # dos meses completos = dos nóminas
    assert an.nominas(empleados, "2026-08-01", "2026-09-30") == pytest.approx(3000)


def test_kpis_de_septiembre(datos):
    k = an.kpis(datos, "2026-09-01", "2026-09-30")
    assert k["ingresos"] == 25 + 120
    assert k["servicios"] == 2
    assert k["ticket_medio"] == pytest.approx(72.5)
    assert k["clientes_atendidos"] == 2
    assert k["costes"] == pytest.approx(850 + 100 + 70 + 1500)
    assert k["beneficio"] == pytest.approx(145 - 2520)
    assert k["margen"] == pytest.approx((145 - 2520) / 145)


def test_kpis_sin_ventas_no_dividen_por_cero(datos):
    datos["ventas"] = datos["ventas"].iloc[0:0]
    k = an.kpis(datos, "2026-09-01", "2026-09-30")
    assert k["ingresos"] == 0 and k["ticket_medio"] == 0 and k["margen"] == 0


def test_periodo_anterior_tiene_la_misma_duracion():
    desde, hasta = an.periodo_anterior("2026-09-01", "2026-09-30")
    assert (desde, hasta) == (d("2026-08-02"), d("2026-08-31"))


def test_serie_mensual_un_registro_por_mes(datos):
    serie = an.serie_mensual(datos, "2026-06-01", "2026-09-30")
    assert list(serie["mes"].dt.strftime("%Y-%m")) == ["2026-06", "2026-07", "2026-08", "2026-09"]
    assert serie.loc[serie["mes"] == d("2026-07-01"), "ingresos"].iloc[0] == 55 + 90


def test_ingresos_por_servicio_y_profesional(datos):
    por_servicio = an.ingresos_por_servicio(datos, "2026-01-01", "2026-09-30")
    assert por_servicio.iloc[0]["servicio"] == "Balayage"
    assert por_servicio.loc[por_servicio["servicio"] == "Corte mujer", "servicios"].iloc[0] == 2

    por_profesional = an.ingresos_por_profesional(datos, "2026-01-01", "2026-09-30")
    assert por_profesional.iloc[0]["empleado"] == "Marta"          # 55 + 120 + 90 = 265
    assert por_profesional.iloc[0]["ingresos"] == 265


def test_costes_por_categoria_incluye_compras_y_nominas(datos):
    costes = an.costes_por_categoria(datos, "2026-09-01", "2026-09-30").set_index("categoria")["importe"]
    assert costes["Alquiler"] == 850
    assert costes["Compras a proveedores"] == 70
    assert costes["Nóminas"] == pytest.approx(1500)


def test_rentabilidad_por_hora(datos):
    r = an.rentabilidad_servicios(datos).set_index("nombre")["euros_por_hora"]
    assert r["Corte mujer"] == pytest.approx(25 / 45 * 60)
    assert r["Balayage"] == pytest.approx(120 / 210 * 60)


# ---------------- clientes ----------------

def test_segmentos_de_clientes(datos):
    resumen = an.resumen_clientes(datos, HOY).set_index("id_cliente")
    assert resumen.loc[1, "segmento"] == "Recurrente"
    assert resumen.loc[2, "segmento"] == "Nueva"
    assert resumen.loc[3, "segmento"] == "Perdida"
    assert resumen.loc[4, "segmento"] == "En riesgo"
    assert resumen.loc[5, "segmento"] == "Sin visitas"
    assert resumen.loc[1, "visitas"] == 3 and resumen.loc[1, "gasto_total"] == 105
    assert resumen.loc[1, "ultimo_servicio"] == "Corte mujer"


def test_tasa_de_repeticion(datos):
    resumen = an.resumen_clientes(datos, HOY)
    # con visitas: 1 (3), 2 (1), 3 (2), 4 (1) -> vuelven 2 de 4
    assert an.tasa_repeticion(resumen) == pytest.approx(0.5)


def test_lista_de_reactivacion_ordenada_por_gasto(datos):
    resumen = an.resumen_clientes(datos, HOY)
    lista = an.lista_reactivacion(resumen, 60)
    assert list(lista["nombre"]) == ["Dora Pons", "Carla Sanz"]      # 90 € y 36 €
    assert an.lista_reactivacion(resumen, 100)["nombre"].tolist() == ["Carla Sanz"]


def test_sin_ventas_el_resumen_de_clientes_funciona(datos):
    datos["ventas"] = datos["ventas"].iloc[0:0]
    resumen = an.resumen_clientes(datos, HOY)
    assert set(resumen["segmento"]) == {"Sin visitas"}
    assert an.tasa_repeticion(resumen) == 0
    assert an.lista_reactivacion(resumen).empty


def test_nuevos_por_mes(datos):
    nuevos = an.nuevos_por_mes(datos, "2026-08-01", "2026-09-30").set_index(
        an.nuevos_por_mes(datos, "2026-08-01", "2026-09-30")["mes"].dt.strftime("%Y-%m"))
    assert nuevos.loc["2026-08", "clientes_nuevos"] == 0
    assert nuevos.loc["2026-09", "clientes_nuevos"] == 2


# ---------------- agenda ----------------

def test_ocupacion_cuenta_solo_citas_confirmadas(datos):
    o = an.ocupacion(datos, "2026-09-28", "2026-09-28", HOY).set_index("empleado")
    assert o.loc["Alba", "minutos_disponibles"] == 600                 # 09:30 a 19:30
    assert o.loc["Alba", "minutos_reservados"] == 120
    assert o.loc["Alba", "ocupacion"] == pytest.approx(0.2)
    assert o.loc["Marta", "minutos_reservados"] == 0                  # su cita está cancelada


def test_ocupacion_no_cuenta_dias_futuros(datos):
    o = an.ocupacion(datos, "2026-09-28", "2026-12-31", HOY).set_index("empleado")
    dias_laborables = 2                                              # lunes 28 y martes 29
    assert o.loc["Alba", "minutos_disponibles"] == 600 * dias_laborables


def test_mapa_de_horas_tiene_la_rejilla_completa(datos):
    mapa = an.mapa_de_horas(datos, "2026-09-28", "2026-09-28")
    assert len(mapa) == 5 * 11 + 5                                    # L-V 9..19 y sábado 9..13
    assert mapa.loc[(mapa["dia"] == "lunes") & (mapa["hora"] == 9), "citas"].iloc[0] == 1
    assert mapa.loc[(mapa["dia"] == "lunes") & (mapa["hora"] == 11), "citas"].iloc[0] == 1
    assert "domingo" not in set(mapa["dia"])


def test_origen_y_cancelaciones(datos):
    origen = an.origen_reservas(datos, "2026-09-28", "2026-09-28").set_index("origen")["citas"]
    assert origen["Teléfono"] == 1 and origen["Web (asistente)"] == 1      # la cancelada no cuenta
    assert an.tasa_cancelacion(datos, "2026-09-28", "2026-09-28") == pytest.approx(1 / 3)


# ---------------- marketing ----------------

def test_coste_por_cliente_nuevo(datos):
    m = an.marketing_mensual(datos, "2026-09-01", "2026-09-30")
    assert m.iloc[0]["gasto_marketing"] == 100
    assert m.iloc[0]["clientes_nuevos"] == 2
    assert m.iloc[0]["coste_por_cliente_nuevo"] == pytest.approx(50)


def test_mes_sin_clientes_nuevos_no_da_coste(datos):
    m = an.marketing_mensual(datos, "2026-08-01", "2026-08-31")
    assert pd.isna(m.iloc[0]["coste_por_cliente_nuevo"])


def test_ideas_devuelve_frases_con_datos(datos):
    frases = an.ideas(datos, "2026-09-01", "2026-09-30", HOY)
    assert frases and all(isinstance(f, str) for f in frases)
    assert any("sin venir" in f for f in frases)                 # hay clientes en riesgo y perdidos
    assert any("Balayage" in f or "Corte mujer" in f for f in frases)
