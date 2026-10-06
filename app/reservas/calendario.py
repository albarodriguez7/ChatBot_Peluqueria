"""
Espejo de solo lectura hacia Google Calendar.

La base de datos es la fuente de verdad. Este módulo refleja en el calendario
de cada profesional sus citas confirmadas y sus bloqueos, para que las vea en el
móvil. Lo que se escriba a mano en Google Calendar NO llega a la base de datos
y NO bloquea huecos: para apuntar o bloquear se usa el panel del personal.

Cómo funciona: en cada sincronización se calcula lo que debería haber en cada
calendario (los próximos 90 días) y se compara con lo que hay. Solo se tocan los
eventos creados por esta aplicación (llevan una marca privada); los eventos que
las empleadas creen por su cuenta no se leen ni se borran nunca.

Configuración (.env):
    GOOGLE_SERVICE_ACCOUNT_FILE=credenciales/google_service_account.json
    GCAL_EMPLEADO_1=<id del calendario de la empleada 1>
    GCAL_EMPLEADO_2=<id del calendario de la empleada 2>
"""

import logging
import os
import threading
from datetime import datetime, time, timedelta
from pathlib import Path

import pandas as pd

from reservas import config, db
from reservas.disponibilidad import cargar_servicios, ids_empleados, nombre_empleado

log = logging.getLogger(__name__)

MARCA_APP = "studio_alba"
DIAS_VENTANA = 90
COLOR_BLOQUEO = "8"  # gris grafito en Google Calendar
ORIGEN_ETIQUETAS = {"asistente": "web", "telefono": "teléfono", "tienda": "tienda"}


class CalendarioNoConfigurado(RuntimeError):
    pass


# ============================================================
# CONFIGURACIÓN
# ============================================================

def ruta_credenciales():
    valor = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()

    if not valor:
        return None

    ruta = Path(valor)

    return ruta if ruta.is_absolute() else config.BASE_DIR / ruta


def calendarios_configurados():
    """{id_empleado: id_calendario} para las empleadas que tienen calendario."""
    calendarios = {}

    for id_empleado in ids_empleados():
        valor = os.getenv(f"GCAL_EMPLEADO_{id_empleado}", "").strip()

        if valor:
            calendarios[id_empleado] = valor

    return calendarios


def habilitado():
    ruta = ruta_credenciales()

    return bool(ruta and ruta.exists() and calendarios_configurados())


# ============================================================
# LO QUE DEBERÍA HABER EN CADA CALENDARIO
# ============================================================

def _instante(fecha, hora):
    horas, minutos = map(int, hora.split(":"))

    return datetime.combine(
        pd.to_datetime(fecha).date(),
        time(horas, minutos),
        tzinfo=config.ZONA_HORARIA,
    )


def _evento(clave, resumen, descripcion, fecha, hora_inicio, hora_fin, color=None):
    zona = str(config.ZONA_HORARIA)

    evento = {
        "summary": resumen,
        "description": descripcion,
        "start": {"dateTime": _instante(fecha, hora_inicio).isoformat(), "timeZone": zona},
        "end": {"dateTime": _instante(fecha, hora_fin).isoformat(), "timeZone": zona},
        "reminders": {"useDefault": False},
        "extendedProperties": {"private": {"app": MARCA_APP, "clave": clave}},
    }

    if color:
        evento["colorId"] = color

    return evento


def eventos_deseados(desde, hasta):
    """
    Eventos que deberían existir entre las fechas desde (incluida) y hasta (excluida).
    Devuelve {id_empleado: {clave: evento}}.
    """
    servicios = cargar_servicios().set_index("id_servicio")["nombre"].to_dict()

    citas = db.leer(
        "SELECT c.*, cl.nombre AS cliente, cl.telefono "
        "FROM citas c JOIN clientes cl ON cl.id_cliente = c.id_cliente "
        "WHERE c.estado = 'confirmada' AND c.fecha >= ? AND c.fecha < ?",
        (str(desde), str(hasta)),
    )

    bloqueos = db.leer(
        "SELECT * FROM bloqueos WHERE fecha >= ? AND fecha < ?",
        (str(desde), str(hasta)),
    )

    deseados = {}

    for _, c in citas.iterrows():
        clave = f"cita-{int(c['id_cita'])}"
        servicio = servicios.get(int(c["id_servicio"]), "Servicio")

        deseados.setdefault(int(c["id_empleado"]), {})[clave] = _evento(
            clave,
            f"{c['cliente']} · {servicio}",
            f"Teléfono: {c['telefono']}\n"
            f"Reservada por: {ORIGEN_ETIQUETAS.get(c['origen'], c['origen'])}\n"
            f"Cita nº {int(c['id_cita'])}",
            c["fecha"], c["hora_inicio"], c["hora_fin"],
        )

    for _, b in bloqueos.iterrows():
        clave = f"bloqueo-{int(b['id_bloqueo'])}"
        motivo = b["motivo"] or "sin motivo"

        deseados.setdefault(int(b["id_empleado"]), {})[clave] = _evento(
            clave,
            f"Bloqueado: {motivo}",
            "Hueco bloqueado desde el panel. No se ofrece a los clientes.",
            b["fecha"], b["hora_inicio"], b["hora_fin"],
            color=COLOR_BLOQUEO,
        )

    return deseados


# ============================================================
# COMPARAR LO DESEADO CON LO QUE HAY (sin tocar Google)
# ============================================================

def _instante_de_evento(campo):
    return datetime.fromisoformat(campo["dateTime"])


def _iguales(existente, deseado):
    try:
        return (
            existente.get("summary") == deseado["summary"]
            and (existente.get("description") or "").strip() == deseado["description"].strip()
            and _instante_de_evento(existente["start"]) == _instante_de_evento(deseado["start"])
            and _instante_de_evento(existente["end"]) == _instante_de_evento(deseado["end"])
            and existente.get("colorId") == deseado.get("colorId")
        )
    except (KeyError, ValueError):
        return False


def calcular_operaciones(deseados, existentes):
    """
    deseados: {clave: evento}. existentes: eventos de la aplicación que hay ahora
    en el calendario. Devuelve (crear, actualizar, borrar).
    """
    por_clave = {}
    sobrantes = []

    for evento in existentes:
        clave = evento.get("extendedProperties", {}).get("private", {}).get("clave")

        if not clave:
            continue

        if clave in por_clave:
            sobrantes.append(evento["id"])        # duplicado: nos quedamos con el primero
        else:
            por_clave[clave] = evento

    crear = [e for clave, e in deseados.items() if clave not in por_clave]

    actualizar = [
        (por_clave[clave]["id"], e)
        for clave, e in deseados.items()
        if clave in por_clave and not _iguales(por_clave[clave], e)
    ]

    borrar = sobrantes + [
        e["id"] for clave, e in por_clave.items() if clave not in deseados
    ]

    return crear, actualizar, borrar


# ============================================================
# GOOGLE CALENDAR
# ============================================================

class GoogleCalendar:
    """Adaptador fino sobre la API de Google. Los tests usan uno falso en su lugar."""

    def __init__(self, ruta=None, servicio=None):
        self._ruta = ruta
        self._servicio_api = servicio

    def _servicio(self):
        if self._servicio_api is None:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            credenciales = service_account.Credentials.from_service_account_file(
                str(self._ruta),
                scopes=["https://www.googleapis.com/auth/calendar"],
            )
            self._servicio_api = build(
                "calendar", "v3", credentials=credenciales, cache_discovery=False
            )

        return self._servicio_api

    def listar(self, id_calendario, desde, hasta):
        eventos, pagina = [], None

        while True:
            respuesta = self._servicio().events().list(
                calendarId=id_calendario,
                timeMin=desde.isoformat(),
                timeMax=hasta.isoformat(),
                singleEvents=True,
                maxResults=250,
                pageToken=pagina,
                privateExtendedProperty=f"app={MARCA_APP}",
            ).execute()

            eventos.extend(respuesta.get("items", []))
            pagina = respuesta.get("nextPageToken")

            if not pagina:
                return eventos

    def crear(self, id_calendario, evento):
        return self._servicio().events().insert(
            calendarId=id_calendario, body=evento
        ).execute()

    def actualizar(self, id_calendario, id_evento, evento):
        return self._servicio().events().update(
            calendarId=id_calendario, eventId=id_evento, body=evento
        ).execute()

    def borrar(self, id_calendario, id_evento):
        try:
            self._servicio().events().delete(
                calendarId=id_calendario, eventId=id_evento
            ).execute()
        except Exception as error:
            # Si ya no existe (404/410), el resultado es el que queríamos.
            estado = getattr(getattr(error, "resp", None), "status", None)
            if estado not in (404, 410):
                raise


def _cliente_por_defecto():
    if not habilitado():
        raise CalendarioNoConfigurado(
            "Google Calendar no está configurado: revisa GOOGLE_SERVICE_ACCOUNT_FILE "
            "y GCAL_EMPLEADO_<n> en el .env."
        )

    return GoogleCalendar(ruta_credenciales())


# ============================================================
# SINCRONIZAR
# ============================================================

def sincronizar(cliente=None):
    """
    Deja los calendarios como dice la base de datos.
    Devuelve {'creados': n, 'actualizados': n, 'borrados': n, 'errores': [...]}.
    """
    cliente = cliente or _cliente_por_defecto()

    desde = config.ahora().replace(hour=0, minute=0, second=0, microsecond=0)
    hasta = desde + timedelta(days=DIAS_VENTANA)

    desde_aware = desde.replace(tzinfo=config.ZONA_HORARIA)
    hasta_aware = hasta.replace(tzinfo=config.ZONA_HORARIA)

    deseados = eventos_deseados(desde.date(), hasta.date())

    resumen = {"creados": 0, "actualizados": 0, "borrados": 0, "errores": []}

    for id_empleado, id_calendario in calendarios_configurados().items():
        nombre = nombre_empleado(id_empleado) or f"empleada {id_empleado}"

        try:
            existentes = cliente.listar(id_calendario, desde_aware, hasta_aware)
        except Exception as error:
            log.exception("No se pudo leer el calendario de %s", nombre)
            resumen["errores"].append(f"{nombre}: {error}")
            continue

        crear, actualizar, borrar = calcular_operaciones(
            deseados.get(id_empleado, {}), existentes
        )

        operaciones = (
            [("creados", lambda e=e: cliente.crear(id_calendario, e)) for e in crear]
            + [("actualizados", lambda i=i, e=e: cliente.actualizar(id_calendario, i, e))
               for i, e in actualizar]
            + [("borrados", lambda i=i: cliente.borrar(id_calendario, i)) for i in borrar]
        )

        # Un evento que falla no impide sincronizar el resto.
        for tipo, operacion in operaciones:
            try:
                operacion()
                resumen[tipo] += 1
            except Exception as error:
                log.exception("Error sincronizando con el calendario de %s", nombre)
                resumen["errores"].append(f"{nombre}: {error}")

    return resumen


def comprobar_acceso(cliente=None):
    """Para cada empleada, comprueba que su calendario se puede leer. Devuelve [(nombre, ok, mensaje)]."""
    cliente = cliente or _cliente_por_defecto()

    ahora = config.ahora().replace(tzinfo=config.ZONA_HORARIA)
    resultados = []

    for id_empleado, id_calendario in calendarios_configurados().items():
        nombre = nombre_empleado(id_empleado) or f"empleada {id_empleado}"

        try:
            cliente.listar(id_calendario, ahora, ahora + timedelta(days=1))
            resultados.append((nombre, True, "Conectado."))
        except Exception as error:
            estado = getattr(getattr(error, "resp", None), "status", None)

            if estado == 404:
                mensaje = (
                    "No se encuentra el calendario. Revisa el ID y que esté compartido "
                    "con la cuenta de servicio."
                )
            elif estado == 403:
                mensaje = (
                    "Sin permiso. Comparte el calendario con la cuenta de servicio con "
                    "«Realizar cambios en eventos» y comprueba que la API de Calendar está activada."
                )
            else:
                mensaje = str(error)

            resultados.append((nombre, False, mensaje))

    return resultados


# ============================================================
# SINCRONIZACIÓN AUTOMÁTICA TRAS CADA CAMBIO
# ============================================================

_estado = threading.Lock()
_ejecutando = False
_pendiente = False


def _bucle():
    global _ejecutando, _pendiente

    while True:
        try:
            resumen = sincronizar()
            if resumen["errores"]:
                log.warning("Sincronización con errores: %s", resumen["errores"])
        except Exception:
            log.exception("Falló la sincronización con Google Calendar")

        with _estado:
            if _pendiente:
                _pendiente = False
                continue
            _ejecutando = False
            return


def solicitar_sincronizacion():
    """
    Pide una sincronización en segundo plano. Nunca bloquea ni lanza errores:
    una reserva no puede fallar porque Google esté caído.
    Si ya hay una en marcha, se encadena otra al terminar (varios cambios seguidos
    se agrupan).
    """
    global _ejecutando, _pendiente

    if not habilitado():
        return

    with _estado:
        if _ejecutando:
            _pendiente = True
            return
        _ejecutando = True

    threading.Thread(target=_bucle, daemon=True, name="sync-google-calendar").start()
