"""Tests del espejo con Google Calendar. Usan un calendario falso en memoria: no llaman a Google."""

import threading
import time
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from reservas import calendario, config
from reservas.bloqueos import crear_bloqueo
from reservas.citas import cancelar_cita, crear_cita, modificar_cita
from reservas.clientes import buscar_o_crear_cliente


class CalendarioFalso:
    """Imita lo justo de Google Calendar: eventos por calendario, con su marca privada."""

    def __init__(self):
        self.eventos = {"cal-alba": {}, "cal-marta": {}}
        self.contador = 0
        self.fallar_en = set()

    def _revisar(self, id_calendario):
        if id_calendario in self.fallar_en:
            raise RuntimeError("Google no responde")

    def listar(self, id_calendario, desde, hasta):
        self._revisar(id_calendario)
        return [
            e for e in self.eventos[id_calendario].values()
            if e.get("extendedProperties", {}).get("private", {}).get("app") == calendario.MARCA_APP
            and desde <= datetime.fromisoformat(e["start"]["dateTime"]) < hasta
        ]

    def crear(self, id_calendario, evento):
        self._revisar(id_calendario)
        self.contador += 1
        nuevo = {**evento, "id": f"ev{self.contador}"}
        self.eventos[id_calendario][nuevo["id"]] = nuevo
        return nuevo

    def actualizar(self, id_calendario, id_evento, evento):
        self._revisar(id_calendario)
        self.eventos[id_calendario][id_evento] = {**evento, "id": id_evento}

    def borrar(self, id_calendario, id_evento):
        self._revisar(id_calendario)
        self.eventos[id_calendario].pop(id_evento, None)

    def claves(self, id_calendario):
        return sorted(
            e["extendedProperties"]["private"]["clave"]
            for e in self.eventos[id_calendario].values()
            if "extendedProperties" in e
        )


@pytest.fixture(autouse=True)
def calendarios(monkeypatch):
    monkeypatch.setenv("GCAL_EMPLEADO_1", "cal-alba")
    monkeypatch.setenv("GCAL_EMPLEADO_2", "cal-marta")
    monkeypatch.setattr(config, "ahora", lambda: datetime(2026, 9, 28, 8, 0))


@pytest.fixture
def google():
    return CalendarioFalso()


def test_sincronizar_crea_los_eventos_de_cada_profesional(google):
    resumen = calendario.sincronizar(google)

    assert resumen["errores"] == []
    assert resumen["creados"] > 0
    # Las citas 7, 8, 10, 15... son de Alba (ids impares) y 18, 4... de Marta (ids pares).
    assert "cita-7" in google.claves("cal-alba")
    assert "cita-18" in google.claves("cal-marta")
    # Las canceladas no aparecen.
    assert "cita-13" not in google.claves("cal-alba")
    assert "cita-14" not in google.claves("cal-marta")


def test_sincronizar_dos_veces_no_cambia_nada(google):
    calendario.sincronizar(google)
    segundo = calendario.sincronizar(google)
    assert (segundo["creados"], segundo["actualizados"], segundo["borrados"]) == (0, 0, 0)


def test_el_evento_lleva_cliente_servicio_y_telefono(google):
    calendario.sincronizar(google)
    evento = next(
        e for e in google.eventos["cal-alba"].values()
        if e["extendedProperties"]["private"]["clave"] == "cita-7"
    )
    assert " · " in evento["summary"]                      # "Cliente · Servicio"
    assert "Teléfono:" in evento["description"]
    assert evento["start"]["dateTime"].startswith("2026-09-29T09:30")
    assert evento["start"]["timeZone"] == "Europe/Madrid"


def test_nueva_cita_y_cancelacion(google):
    calendario.sincronizar(google)
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    id_cita = crear_cita(c1, 2, "2026-10-13", "10:00", id_empleado=1)

    calendario.sincronizar(google)
    assert f"cita-{id_cita}" in google.claves("cal-alba")

    cancelar_cita(id_cita, c1)
    resumen = calendario.sincronizar(google)
    assert f"cita-{id_cita}" not in google.claves("cal-alba")
    assert resumen["borrados"] == 1


def test_mover_una_cita_actualiza_el_evento(google):
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    id_cita = crear_cita(c1, 2, "2026-10-13", "10:00", id_empleado=1)
    calendario.sincronizar(google)

    modificar_cita(id_cita, c1, "2026-10-13", "12:00")
    resumen = calendario.sincronizar(google)

    assert resumen["actualizados"] == 1
    evento = next(
        e for e in google.eventos["cal-alba"].values()
        if e["extendedProperties"]["private"]["clave"] == f"cita-{id_cita}"
    )
    assert evento["start"]["dateTime"].startswith("2026-10-13T12:00")


def test_si_cambia_de_profesional_el_evento_se_mueve_de_calendario(google):
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    c2 = buscar_o_crear_cliente("Bea", "611000002")
    id_cita = crear_cita(c1, 2, "2026-10-13", "10:00", id_empleado=1)
    calendario.sincronizar(google)

    # Alba se bloquea esa hora para otro asunto y la cita se traslada con Marta.
    cancelar_cita(id_cita, c1)
    id_nueva = crear_cita(c2, 2, "2026-10-13", "10:00", id_empleado=2)
    calendario.sincronizar(google)

    assert f"cita-{id_cita}" not in google.claves("cal-alba")
    assert f"cita-{id_nueva}" in google.claves("cal-marta")


def test_los_bloqueos_aparecen_y_desaparecen(google):
    id_bloqueo = crear_bloqueo(1, "2026-10-13", "14:00", "15:00", "comida")
    calendario.sincronizar(google)

    assert f"bloqueo-{id_bloqueo}" in google.claves("cal-alba")
    evento = next(iter(
        e for e in google.eventos["cal-alba"].values()
        if e["extendedProperties"]["private"]["clave"] == f"bloqueo-{id_bloqueo}"
    ))
    assert evento["summary"] == "Bloqueado: comida"

    from reservas.bloqueos import eliminar_bloqueo
    eliminar_bloqueo(id_bloqueo)
    calendario.sincronizar(google)
    assert f"bloqueo-{id_bloqueo}" not in google.claves("cal-alba")


def test_los_eventos_de_las_empleadas_no_se_tocan(google):
    propio = {
        "id": "mio", "summary": "Dentista",
        "start": {"dateTime": "2026-10-13T09:00:00+02:00"},
        "end": {"dateTime": "2026-10-13T10:00:00+02:00"},
    }
    google.eventos["cal-alba"]["mio"] = propio

    calendario.sincronizar(google)
    assert "mio" in google.eventos["cal-alba"]     # sigue ahí, sin marca de la app


def test_un_evento_editado_a_mano_vuelve_a_su_sitio(google):
    calendario.sincronizar(google)
    id_evento = next(
        e["id"] for e in google.eventos["cal-alba"].values()
        if e["extendedProperties"]["private"]["clave"] == "cita-7"
    )
    google.eventos["cal-alba"][id_evento]["start"]["dateTime"] = "2026-09-29T17:00:00+02:00"

    resumen = calendario.sincronizar(google)

    assert resumen["actualizados"] == 1
    assert google.eventos["cal-alba"][id_evento]["start"]["dateTime"].startswith("2026-09-29T09:30")


def test_los_duplicados_se_eliminan(google):
    calendario.sincronizar(google)
    original = next(iter(google.eventos["cal-alba"].values()))
    google.contador += 1
    google.eventos["cal-alba"]["dup"] = {**original, "id": "dup"}

    resumen = calendario.sincronizar(google)
    assert resumen["borrados"] == 1


def test_citas_lejanas_quedan_fuera_de_la_ventana(google):
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    lejana = crear_cita(c1, 2, "2027-03-02", "10:00", id_empleado=1)   # a más de 90 días
    calendario.sincronizar(google)

    assert f"cita-{lejana}" not in google.claves("cal-alba")


def test_los_dias_pasados_no_se_sincronizan(google, monkeypatch):
    monkeypatch.setattr(config, "ahora", lambda: datetime(2026, 9, 30, 8, 0))
    calendario.sincronizar(google)

    claves = google.claves("cal-alba") + google.claves("cal-marta")
    assert "cita-9" not in claves          # 28/09
    assert "cita-7" not in claves          # 29/09
    assert "cita-10" in claves             # 30/09


def test_un_calendario_caido_no_impide_sincronizar_el_otro(google):
    google.fallar_en.add("cal-alba")
    resumen = calendario.sincronizar(google)

    assert len(resumen["errores"]) == 1 and "Alba" in resumen["errores"][0]
    assert google.claves("cal-marta")            # Marta sí se ha sincronizado
    assert google.claves("cal-alba") == []


def test_empleada_sin_calendario_se_ignora(google, monkeypatch):
    monkeypatch.delenv("GCAL_EMPLEADO_2")
    calendario.sincronizar(google)
    assert google.claves("cal-marta") == []
    assert google.claves("cal-alba")


# ---------------- configuración ----------------

def test_no_esta_habilitado_sin_configuracion(monkeypatch):
    monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_FILE", raising=False)
    assert calendario.habilitado() is False
    with pytest.raises(calendario.CalendarioNoConfigurado):
        calendario.sincronizar()


def test_habilitado_con_credenciales_y_calendarios(monkeypatch, tmp_path):
    credenciales = tmp_path / "cuenta.json"
    credenciales.write_text("{}")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_FILE", str(credenciales))
    assert calendario.habilitado() is True


def test_sin_configurar_las_reservas_funcionan_igual():
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    assert crear_cita(c1, 2, "2026-10-13", "10:00") > 0        # no hay hilo ni error


def test_solicitudes_seguidas_se_agrupan(monkeypatch):
    llamadas, dentro, liberar = [], threading.Event(), threading.Event()

    def sincronizar_lento():
        llamadas.append(1)
        dentro.set()
        liberar.wait(timeout=5)
        return {"errores": []}

    monkeypatch.setattr(calendario, "habilitado", lambda: True)
    monkeypatch.setattr(calendario, "sincronizar", sincronizar_lento)

    calendario.solicitar_sincronizacion()
    assert dentro.wait(timeout=5)
    for _ in range(5):                       # cinco cambios mientras hay una en marcha
        calendario.solicitar_sincronizacion()
    liberar.set()

    for _ in range(50):
        if not calendario._ejecutando:
            break
        time.sleep(0.05)

    assert len(llamadas) == 2                # la de arriba + una sola de repaso


def test_un_fallo_de_google_no_rompe_la_reserva(monkeypatch):
    monkeypatch.setattr(calendario, "habilitado", lambda: True)
    monkeypatch.setattr(calendario, "sincronizar", MagicMock(side_effect=RuntimeError("caído")))
    c1 = buscar_o_crear_cliente("Ana", "611000001")
    assert crear_cita(c1, 2, "2026-10-13", "10:00") > 0
    for _ in range(50):
        if not calendario._ejecutando:
            break
        time.sleep(0.05)


# ---------------- adaptador con la API de Google (simulada) ----------------

def test_el_adaptador_llama_a_la_api_con_lo_esperado():
    servicio = MagicMock()
    eventos = servicio.events.return_value
    eventos.list.return_value.execute.side_effect = [
        {"items": [{"id": "a"}], "nextPageToken": "p2"},
        {"items": [{"id": "b"}]},
    ]
    google = calendario.GoogleCalendar(servicio=servicio)

    desde = datetime(2026, 9, 28, tzinfo=config.ZONA_HORARIA)
    resultado = google.listar("cal", desde, desde)

    assert [e["id"] for e in resultado] == ["a", "b"]                        # pagina
    argumentos = eventos.list.call_args_list[0].kwargs
    assert argumentos["privateExtendedProperty"] == "app=studio_alba"       # solo nuestros eventos
    assert argumentos["singleEvents"] is True

    google.crear("cal", {"summary": "x"})
    assert eventos.insert.call_args.kwargs == {"calendarId": "cal", "body": {"summary": "x"}}


def test_borrar_un_evento_que_ya_no_existe_no_es_error():
    servicio = MagicMock()
    error = Exception("gone")
    error.resp = MagicMock(status=410)
    servicio.events.return_value.delete.return_value.execute.side_effect = error
    calendario.GoogleCalendar(servicio=servicio).borrar("cal", "ev")        # no lanza

    error.resp.status = 500
    with pytest.raises(Exception):
        calendario.GoogleCalendar(servicio=servicio).borrar("cal", "ev")


def test_comprobar_acceso_explica_los_errores_habituales(google):
    class Error(Exception):
        def __init__(self, estado):
            self.resp = MagicMock(status=estado)

    google.fallar_en = set()
    original = google.listar

    def listar(id_calendario, desde, hasta):
        if id_calendario == "cal-alba":
            raise Error(404)
        raise Error(403)

    google.listar = listar
    resultados = dict((n, (ok, m)) for n, ok, m in calendario.comprobar_acceso(google))

    assert resultados["Alba"][0] is False and "ID" in resultados["Alba"][1]
    assert resultados["Marta"][0] is False and "permiso" in resultados["Marta"][1].lower()
    google.listar = original
