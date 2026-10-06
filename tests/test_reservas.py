import threading
from datetime import datetime

import pandas as pd
import pytest

from reservas import config, sesion
from reservas.citas import cancelar_cita, crear_cita, modificar_cita
from reservas.clientes import (
    buscar_cliente_por_telefono,
    buscar_o_crear_cliente,
    normalizar_telefono,
)
from reservas.disponibilidad import buscar_horarios_disponibles, cargar_citas


@pytest.fixture
def hoy_fijo(monkeypatch):
    """Lunes 28/09/2026, 08:00 en Madrid."""
    monkeypatch.setattr(config, "ahora", lambda: datetime(2026, 9, 28, 8, 0))


# ---------------- horario ----------------

def test_horario_usa_el_horario_del_negocio(hoy_fijo):
    horas = buscar_horarios_disponibles(id_servicio=2, fecha="2026-10-13")  # martes sin citas
    assert horas[0] == "09:30"
    assert horas[-1] == "19:00"          # corte de 30 min: última entrada 19:00


def test_domingo_cerrado(hoy_fijo):
    assert buscar_horarios_disponibles(id_servicio=2, fecha="2026-10-04") == []


def test_sabado_cierra_a_las_14(hoy_fijo):
    horas = buscar_horarios_disponibles(id_servicio=2, fecha="2026-10-10")
    assert horas[-1] == "13:30"


def test_no_ofrece_horas_pasadas_hoy(monkeypatch):
    monkeypatch.setattr(config, "ahora", lambda: datetime(2026, 10, 13, 12, 0))
    horas = buscar_horarios_disponibles(id_servicio=2, fecha="2026-10-13")
    assert all(h > "12:00" for h in horas)


def test_no_ofrece_dias_pasados(hoy_fijo):
    assert buscar_horarios_disponibles(id_servicio=2, fecha="2026-09-01") == []


# ---------------- capacidad por profesional ----------------

def test_dos_profesionales_permiten_dos_citas_a_la_misma_hora(hoy_fijo):
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    c2 = buscar_o_crear_cliente("Bea", "611000002")
    c3 = buscar_o_crear_cliente("Cris", "611000003")

    crear_cita(c1, 2, "2026-10-13", "10:00")
    crear_cita(c2, 2, "2026-10-13", "10:00")

    # Con las dos ocupadas, esa hora ya no se ofrece ni se puede reservar.
    assert "10:00" not in buscar_horarios_disponibles(2, "2026-10-13")
    with pytest.raises(ValueError):
        crear_cita(c3, 2, "2026-10-13", "10:00")


def test_profesional_concreta_ocupada(hoy_fijo):
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    c2 = buscar_o_crear_cliente("Bea", "611000002")

    crear_cita(c1, 2, "2026-10-13", "10:00", id_empleado=1)

    assert "10:00" not in buscar_horarios_disponibles(2, "2026-10-13", id_empleado=1)
    assert "10:00" in buscar_horarios_disponibles(2, "2026-10-13", id_empleado=2)
    with pytest.raises(ValueError):
        crear_cita(c2, 2, "2026-10-13", "10:00", id_empleado=1)


def test_la_cita_guarda_id_empleado(hoy_fijo):
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    crear_cita(c1, 2, "2026-10-13", "10:00")
    citas = cargar_citas()
    assert citas.iloc[-1]["id_empleado"] in (1, 2)


def test_cliente_inexistente_no_puede_reservar(hoy_fijo):
    with pytest.raises(ValueError):
        crear_cita(9999, 2, "2026-10-13", "10:00")


# ---------------- modificar / cancelar ----------------

def test_modificar_no_choca_con_la_propia_cita(hoy_fijo):
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    id_cita = crear_cita(c1, 2, "2026-10-13", "10:00")
    modificar_cita(id_cita, c1, "2026-10-13", "10:30")   # solapa con su propia hora
    citas = cargar_citas()
    assert citas[citas.id_cita == id_cita].iloc[0]["hora_inicio"] == "10:30"


def test_no_se_puede_cancelar_cita_ajena(hoy_fijo):
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    c2 = buscar_o_crear_cliente("Bea", "611000002")
    id_cita = crear_cita(c1, 2, "2026-10-13", "10:00")
    with pytest.raises(ValueError):
        cancelar_cita(id_cita, c2)


def test_cancelar_libera_el_hueco(hoy_fijo):
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    c2 = buscar_o_crear_cliente("Bea", "611000002")
    a = crear_cita(c1, 2, "2026-10-13", "10:00", id_empleado=1)
    crear_cita(c2, 2, "2026-10-13", "10:00", id_empleado=2)
    assert "10:00" not in buscar_horarios_disponibles(2, "2026-10-13")
    cancelar_cita(a, c1)
    assert "10:00" in buscar_horarios_disponibles(2, "2026-10-13")


# ---------------- clientes ----------------

def test_telefono_se_normaliza():
    assert normalizar_telefono("+34 600 10 01 01") == "600100101"
    assert normalizar_telefono("0034600100101") == "600100101"
    assert normalizar_telefono("600-100-101") == "600100101"
    assert normalizar_telefono("600100101.0") == "600100101"


def test_cliente_sin_email_se_encuentra_por_telefono():
    # Laura García (id 1) no tiene email en los datos.
    assert buscar_cliente_por_telefono("600 100 101")["id_cliente"] == 1


def test_no_duplica_clientes():
    a = buscar_o_crear_cliente("Ana", "622000000")
    b = buscar_o_crear_cliente("Ana P.", "+34 622 000 000")
    assert a == b


def test_cliente_nuevo_necesita_nombre():
    with pytest.raises(ValueError):
        buscar_o_crear_cliente("", "633000000")


# ---------------- herramientas: el cliente lo fija el código ----------------

def test_herramientas_no_actuan_sin_cliente_identificado(hoy_fijo):
    pytest.importorskip("langchain")
    from tools.reservas_tools import cancelar_cita_tool, reservar_cita

    cfg = {"configurable": {"thread_id": "sin-identificar"}}
    assert "identificado" in cancelar_cita_tool.invoke({"id_cita": 1}, config=cfg)
    assert "identificado" in reservar_cita.invoke(
        {"id_servicio": 2, "fecha": "2026-10-13", "hora_inicio": "10:00"}, config=cfg
    )


def test_un_cliente_no_puede_cancelar_la_cita_de_otro(hoy_fijo):
    pytest.importorskip("langchain")
    from tools.reservas_tools import buscar_cliente, cancelar_cita_tool

    id_ajeno = buscar_o_crear_cliente("Ajena", "644000001")
    id_cita = crear_cita(id_ajeno, 2, "2026-10-13", "10:00")

    cfg = {"configurable": {"thread_id": "conversacion-atacante"}}
    buscar_cliente.invoke({"telefono": "600100101"}, config=cfg)   # se identifica como Laura

    respuesta = cancelar_cita_tool.invoke({"id_cita": id_cita}, config=cfg)
    assert "No se ha podido cancelar" in respuesta

    citas = cargar_citas()
    assert citas[citas.id_cita == id_cita].iloc[0]["estado"] == "confirmada"
    sesion.olvidar("conversacion-atacante")


# ---------------- SQLite ----------------

def test_migracion_desde_csv_y_citas_huerfanas():
    citas = cargar_citas()
    assert len(citas) == 15                       # 17 en el CSV, menos 2 huérfanas
    assert set(citas["id_empleado"]) <= {1, 2}
    assert (config.DATA_DIR / "citas_huerfanas.csv").exists()
    huerfanas = pd.read_csv(config.DATA_DIR / "citas_huerfanas.csv")
    assert sorted(huerfanas["id_cita"]) == [6, 16]


def test_los_datos_persisten_entre_conexiones(hoy_fijo):
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    id_cita = crear_cita(c1, 2, "2026-10-13", "10:00")
    assert id_cita in cargar_citas()["id_cita"].tolist()


def test_reservas_simultaneas_no_ocupan_el_mismo_hueco(hoy_fijo):
    """Seis personas piden la misma hora a la vez: solo caben dos (Alba y Marta)."""
    clientes = [buscar_o_crear_cliente(f"C{i}", f"66000000{i}") for i in range(6)]
    resultados = []

    def reservar(id_cliente):
        try:
            crear_cita(id_cliente, 2, "2026-10-13", "10:00")
            resultados.append("ok")
        except ValueError:
            resultados.append("no")

    hilos = [threading.Thread(target=reservar, args=(c,)) for c in clientes]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert resultados.count("ok") == 2
    citas = cargar_citas()
    del_dia = citas[(citas.fecha == "2026-10-13") & (citas.hora_inicio == "10:00")]
    assert sorted(del_dia["id_empleado"]) == [1, 2]


# ---------------- bloqueos y citas del personal ----------------

from reservas.bloqueos import (  # noqa: E402
    bloquear_dia_completo,
    crear_bloqueo,
    eliminar_bloqueo,
)
from reservas.citas import cancelar_cita_como_empleada  # noqa: E402


def test_bloqueo_quita_huecos_solo_a_esa_profesional(hoy_fijo):
    crear_bloqueo(1, "2026-10-13", "14:00", "15:00", "comida")

    assert "14:00" not in buscar_horarios_disponibles(2, "2026-10-13", id_empleado=1)
    assert "14:00" in buscar_horarios_disponibles(2, "2026-10-13", id_empleado=2)
    # Sin filtrar profesional, sigue habiendo hueco porque Marta está libre.
    assert "14:00" in buscar_horarios_disponibles(2, "2026-10-13")


def test_si_las_dos_bloquean_no_hay_hueco(hoy_fijo):
    crear_bloqueo(1, "2026-10-13", "14:00", "15:00")
    crear_bloqueo(2, "2026-10-13", "14:00", "15:00")
    assert "14:00" not in buscar_horarios_disponibles(2, "2026-10-13")
    assert "14:30" not in buscar_horarios_disponibles(2, "2026-10-13")   # cita de 30 min


def test_dia_completo_bloqueado(hoy_fijo):
    bloquear_dia_completo(1, "2026-10-13", "vacaciones")
    bloquear_dia_completo(2, "2026-10-13", "vacaciones")
    assert buscar_horarios_disponibles(2, "2026-10-13") == []


def test_no_se_bloquea_encima_de_una_cita(hoy_fijo):
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    crear_cita(c1, 2, "2026-10-13", "10:00", id_empleado=1)
    with pytest.raises(ValueError):
        crear_bloqueo(1, "2026-10-13", "09:30", "11:00")
    crear_bloqueo(2, "2026-10-13", "09:30", "11:00")   # otra profesional: sin problema


def test_eliminar_bloqueo_devuelve_los_huecos(hoy_fijo):
    id_bloqueo = crear_bloqueo(1, "2026-10-13", "14:00", "15:00")
    eliminar_bloqueo(id_bloqueo)
    assert "14:00" in buscar_horarios_disponibles(2, "2026-10-13", id_empleado=1)


def test_bloqueo_con_horas_incoherentes_o_en_el_pasado(hoy_fijo):
    with pytest.raises(ValueError):
        crear_bloqueo(1, "2026-10-13", "15:00", "14:00")
    with pytest.raises(ValueError):
        crear_bloqueo(1, "2026-09-01", "10:00", "11:00")


def test_la_reserva_del_asistente_respeta_los_bloqueos(hoy_fijo):
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    crear_bloqueo(1, "2026-10-13", "10:00", "11:00")
    crear_bloqueo(2, "2026-10-13", "10:00", "11:00")
    with pytest.raises(ValueError):
        crear_cita(c1, 2, "2026-10-13", "10:00")


def test_el_personal_puede_apuntar_a_alguien_que_esta_en_la_tienda(monkeypatch):
    monkeypatch.setattr(config, "ahora", lambda: datetime(2026, 10, 13, 12, 5))
    c1 = buscar_o_crear_cliente("Ana", "611000001")

    # El asistente no ofrece horas que ya han empezado...
    with pytest.raises(ValueError):
        crear_cita(c1, 2, "2026-10-13", "12:00")

    # ...pero el personal sí puede, y en tramos de 15 minutos.
    id_cita = crear_cita(
        c1, 2, "2026-10-13", "12:00",
        origen="tienda", intervalo=15, desde_hora_actual=False,
    )
    crear_cita(
        c1, 2, "2026-10-13", "14:15",
        origen="telefono", intervalo=15, desde_hora_actual=False,
    )
    citas = cargar_citas().set_index("id_cita")
    assert citas.loc[id_cita, "origen"] == "tienda"


def test_origen_no_valido(hoy_fijo):
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    with pytest.raises(ValueError):
        crear_cita(c1, 2, "2026-10-13", "10:00", origen="otro")


def test_cancelar_como_empleada(hoy_fijo):
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    id_cita = crear_cita(c1, 2, "2026-10-13", "10:00", origen="telefono")
    cancelar_cita_como_empleada(id_cita)
    assert "10:00" in buscar_horarios_disponibles(2, "2026-10-13")
    with pytest.raises(ValueError):
        cancelar_cita_como_empleada(id_cita)          # ya cancelada


def test_base_de_datos_antigua_se_actualiza_sola(datos_temporales):
    import sqlite3
    from reservas import db

    (datos_temporales / "studio_alba.db").unlink(missing_ok=True)
    con = sqlite3.connect(datos_temporales / "studio_alba.db")
    con.executescript(
        "CREATE TABLE clientes (id_cliente INTEGER PRIMARY KEY, nombre TEXT NOT NULL,"
        " telefono TEXT NOT NULL, email TEXT NOT NULL DEFAULT '', fecha_alta TEXT,"
        " ultimo_servicio TEXT NOT NULL DEFAULT '', total_visitas INTEGER NOT NULL DEFAULT 0);"
        "CREATE TABLE citas (id_cita INTEGER PRIMARY KEY, id_cliente INTEGER NOT NULL,"
        " id_servicio INTEGER NOT NULL, id_empleado INTEGER NOT NULL, fecha TEXT NOT NULL,"
        " hora_inicio TEXT NOT NULL, hora_fin TEXT NOT NULL, estado TEXT NOT NULL);"
        "INSERT INTO clientes (id_cliente, nombre, telefono) VALUES (1, 'Vieja', '600000000');"
        "INSERT INTO citas VALUES (1, 1, 2, 1, '2026-10-13', '10:00', '10:30', 'confirmada');"
    )
    con.commit()
    con.close()
    db._INICIALIZADAS.clear()

    citas = cargar_citas()
    assert "origen" in citas.columns
    assert citas.iloc[0]["origen"] == "asistente"
    assert db.leer("SELECT COUNT(*) AS n FROM bloqueos").iloc[0]["n"] == 0
