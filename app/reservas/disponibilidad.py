import pandas as pd

from reservas import config, db


# ============================================================
# CARGAR DATOS
# ============================================================

def cargar_servicios():
    return pd.read_csv(config.DATA_DIR / "servicios.csv")


def cargar_citas():
    return db.leer("SELECT * FROM citas ORDER BY id_cita")


def cargar_empleados():
    # utf-8-sig: el CSV de empleados lleva BOM y rompería el nombre de la primera columna.
    return pd.read_csv(config.DATA_DIR / "empleados.csv", encoding="utf-8-sig")


def ids_empleados():
    return [int(i) for i in cargar_empleados()["id_empleado"]]


def buscar_empleado_por_nombre(nombre):
    """Devuelve el id_empleado de una profesional por su nombre, o None."""
    nombre = (nombre or "").strip().lower()
    if not nombre:
        return None

    empleados = cargar_empleados()
    coincidencias = empleados[
        empleados["nombre"].astype(str).str.strip().str.lower() == nombre
    ]

    if coincidencias.empty:
        return None

    return int(coincidencias.iloc[0]["id_empleado"])


def nombre_empleado(id_empleado):
    empleados = cargar_empleados()
    fila = empleados[empleados["id_empleado"] == int(id_empleado)]
    return None if fila.empty else str(fila.iloc[0]["nombre"])


# ============================================================
# SERVICIOS
# ============================================================

def obtener_duracion_servicio(id_servicio):
    servicios = cargar_servicios()

    servicio = servicios[servicios["id_servicio"] == id_servicio]

    if servicio.empty:
        raise ValueError("El servicio no existe.")

    return int(servicio.iloc[0]["duracion_minutos"])


# ============================================================
# HORAS
# ============================================================

def hora_a_minutos(hora):
    horas, minutos = map(int, hora.split(":"))
    return horas * 60 + minutos


def minutos_a_hora(minutos):
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


# ============================================================
# CITAS DE UN DÍA
# ============================================================

def obtener_citas_del_dia(fecha):
    fecha = pd.to_datetime(fecha).date().isoformat()

    return db.leer(
        "SELECT * FROM citas WHERE fecha = ? AND estado = 'confirmada'",
        (fecha,),
    )


def obtener_bloqueos_del_dia(fecha):
    fecha = pd.to_datetime(fecha).date().isoformat()

    return db.leer("SELECT * FROM bloqueos WHERE fecha = ?", (fecha,))


# ============================================================
# EMPLEADOS LIBRES EN UN TRAMO
# ============================================================

def empleados_libres(
    citas_del_dia,
    inicio,
    fin,
    id_cita_excluir=None,
    bloqueos_del_dia=None,
):
    """
    Devuelve los id_empleado que no tienen ninguna cita solapada
    con el tramo [inicio, fin) (en minutos).

    Una cita sin id_empleado se considera que bloquea a todo el equipo,
    para no ofrecer huecos que puedan no existir.
    """
    libres = set(ids_empleados())

    for _, cita in citas_del_dia.iterrows():
        if (
            id_cita_excluir is not None
            and int(cita["id_cita"]) == int(id_cita_excluir)
        ):
            continue

        inicio_cita = hora_a_minutos(cita["hora_inicio"])
        fin_cita = hora_a_minutos(cita["hora_fin"])

        if inicio < fin_cita and fin > inicio_cita:
            if "id_empleado" not in cita or pd.isna(cita["id_empleado"]):
                return []
            libres.discard(int(cita["id_empleado"]))

    # Un bloqueo solo afecta a la profesional que lo ha puesto.
    if bloqueos_del_dia is not None:
        for _, bloqueo in bloqueos_del_dia.iterrows():
            inicio_b = hora_a_minutos(bloqueo["hora_inicio"])
            fin_b = hora_a_minutos(bloqueo["hora_fin"])

            if inicio < fin_b and fin > inicio_b:
                libres.discard(int(bloqueo["id_empleado"]))

    return sorted(libres)


# ============================================================
# HORARIOS DISPONIBLES
# ============================================================

def buscar_horarios_disponibles(
    id_servicio,
    fecha,
    intervalo=config.INTERVALO_MINUTOS,
    id_cita_excluir=None,
    id_empleado=None,
    desde_hora_actual=True,
):
    """
    Horas de inicio en las que se puede hacer el servicio.

    desde_hora_actual=False permite ofrecer horas de hoy que ya han empezado
    (para que el personal apunte a un cliente que acaba de entrar en la tienda).

    Si se indica id_empleado, solo cuenta a esa profesional.
    Si no, una hora está disponible cuando al menos una profesional está libre.
    """
    fecha = pd.to_datetime(fecha)

    horario = config.HORARIOS_NEGOCIO.get(fecha.weekday())

    if horario is None:
        return []

    hora_apertura, hora_cierre = horario
    duracion = obtener_duracion_servicio(id_servicio)

    citas = obtener_citas_del_dia(fecha)
    bloqueos = obtener_bloqueos_del_dia(fecha)

    ahora = config.ahora()

    if fecha.date() == ahora.date():
        hora_actual_minutos = (
            ahora.hour * 60 + ahora.minute if desde_hora_actual else None
        )
    elif fecha.date() < ahora.date():
        return []
    else:
        hora_actual_minutos = None

    inicio_jornada = hora_a_minutos(hora_apertura)
    fin_jornada = hora_a_minutos(hora_cierre)

    horarios = []

    for inicio in range(inicio_jornada, fin_jornada, intervalo):

        # Hoy no se ofrecen horas que ya han pasado.
        if hora_actual_minutos is not None and inicio <= hora_actual_minutos:
            continue

        fin = inicio + duracion

        if fin > fin_jornada:
            continue

        libres = empleados_libres(citas, inicio, fin, id_cita_excluir, bloqueos)

        if id_empleado is not None:
            if int(id_empleado) in libres:
                horarios.append(minutos_a_hora(inicio))
        elif libres:
            horarios.append(minutos_a_hora(inicio))

    return horarios


# ============================================================
# DÍAS DISPONIBLES
# ============================================================

def obtener_dias_disponibles(id_servicio, fecha_inicio, numero_dias=30):
    fecha_inicio = pd.to_datetime(fecha_inicio)

    dias_disponibles = []

    for i in range(numero_dias):
        fecha = fecha_inicio + pd.Timedelta(days=i)

        if buscar_horarios_disponibles(id_servicio=id_servicio, fecha=fecha):
            dias_disponibles.append(fecha.date())

    return dias_disponibles


def obtener_proxima_disponibilidad(
    id_servicio,
    fecha_inicio=None,
    numero_dias=90,
    id_empleado=None,
):
    if fecha_inicio is None:
        fecha_inicio = config.ahora().date()
    else:
        fecha_inicio = pd.to_datetime(fecha_inicio).date()

    for i in range(numero_dias):
        fecha = fecha_inicio + pd.Timedelta(days=i)

        horarios = buscar_horarios_disponibles(
            id_servicio=id_servicio,
            fecha=fecha,
            id_empleado=id_empleado,
        )

        if horarios:
            return {"fecha": fecha, "horarios": horarios}

    return None
