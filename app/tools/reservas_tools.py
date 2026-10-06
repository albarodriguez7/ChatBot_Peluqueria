import pandas as pd
from langchain.tools import tool
from langchain_core.runnables import RunnableConfig

from reservas import sesion
from reservas.citas import cancelar_cita, crear_cita, modificar_cita
from reservas.clientes import (
    buscar_cliente_por_telefono,
    buscar_o_crear_cliente,
)
from reservas.disponibilidad import (
    buscar_empleado_por_nombre,
    buscar_horarios_disponibles,
    cargar_citas,
    cargar_servicios,
    nombre_empleado,
    obtener_proxima_disponibilidad,
)

SIN_CLIENTE = (
    "Todavía no se ha identificado al cliente. "
    "Pide su teléfono y usa buscar_cliente (o registrar_cliente si es nuevo)."
)


def _resolver_profesional(profesional):
    """Devuelve (id_empleado, error). Sin nombre => cualquier profesional."""
    if not (profesional or "").strip():
        return None, None

    id_empleado = buscar_empleado_por_nombre(profesional)

    if id_empleado is None:
        return None, f"No hay ninguna profesional llamada {profesional}."

    return id_empleado, None


# ============================================================
# SERVICIOS
# ============================================================

@tool
def consultar_servicios() -> str:
    """
    Consulta los servicios disponibles en Studio Alba,
    incluyendo su identificador, nombre, precio y duración.
    """
    servicios = cargar_servicios()

    if servicios.empty:
        return "No hay servicios disponibles."

    return "\n".join(
        f"id_servicio={int(s['id_servicio'])} | {s['nombre']} | "
        f"{float(s['precio']):.2f} € | {int(s['duracion_minutos'])} minutos"
        for _, s in servicios.iterrows()
    )


# ============================================================
# DISPONIBILIDAD
# ============================================================

@tool
def consultar_disponibilidad(
    id_servicio: int,
    fecha: str,
    profesional: str = "",
) -> str:
    """
    Consulta los horarios disponibles para un servicio en una fecha concreta.

    Args:
        id_servicio: ID del servicio que quiere reservar el cliente.
        fecha: Fecha de la reserva en formato YYYY-MM-DD.
        profesional: Nombre de la profesional, SOLO si el cliente ha pedido
            una en concreto. Si no, déjalo vacío.
    """
    id_empleado, error = _resolver_profesional(profesional)

    if error:
        return error

    try:
        horarios = buscar_horarios_disponibles(
            id_servicio=id_servicio,
            fecha=fecha,
            id_empleado=id_empleado,
        )
    except ValueError as error:
        return f"No se ha podido consultar la disponibilidad: {error}"

    if not horarios:
        return f"No hay horarios disponibles el {fecha}."

    return f"Horarios disponibles el {fecha}: " + ", ".join(horarios)


@tool
def consultar_proxima_disponibilidad(
    id_servicio: int,
    profesional: str = "",
) -> str:
    """
    Busca la primera fecha futura en la que haya disponibilidad para un
    servicio y devuelve los horarios de ese día.

    Args:
        id_servicio: ID del servicio.
        profesional: Nombre de la profesional, SOLO si el cliente la ha pedido.
    """
    id_empleado, error = _resolver_profesional(profesional)

    if error:
        return error

    try:
        resultado = obtener_proxima_disponibilidad(
            id_servicio=id_servicio,
            id_empleado=id_empleado,
        )
    except ValueError as error:
        return f"No se ha podido consultar la disponibilidad: {error}"

    if resultado is None:
        return "No hay disponibilidad en los próximos 90 días."

    return (
        f"La próxima disponibilidad es el "
        f"{resultado['fecha'].strftime('%d/%m/%Y')} a las siguientes horas: "
        f"{', '.join(resultado['horarios'])}."
    )


@tool
def consultar_disponibilidad_modificacion(
    id_cita: int,
    nueva_fecha: str,
    config: RunnableConfig,
) -> str:
    """
    Consulta los horarios disponibles para cambiar una cita existente del
    cliente identificado. La propia cita se excluye de la comprobación.

    Args:
        id_cita: ID de la cita que se quiere cambiar.
        nueva_fecha: Nueva fecha en formato YYYY-MM-DD.
    """
    id_cliente = sesion.cliente_actual(config)

    if id_cliente is None:
        return SIN_CLIENTE

    citas = cargar_citas()

    cita = citas[(citas["id_cita"] == id_cita) & (citas["id_cliente"] == id_cliente)]

    if cita.empty:
        return "No se ha encontrado esa cita para este cliente."

    try:
        horarios = buscar_horarios_disponibles(
            id_servicio=int(cita.iloc[0]["id_servicio"]),
            fecha=nueva_fecha,
            id_cita_excluir=id_cita,
        )
    except ValueError as error:
        return f"No se ha podido consultar la disponibilidad: {error}"

    if not horarios:
        return f"No hay horarios disponibles el {nueva_fecha}."

    return f"Horarios disponibles el {nueva_fecha}: " + ", ".join(horarios)


# ============================================================
# CLIENTE
# ============================================================

@tool
def buscar_cliente(telefono: str, config: RunnableConfig) -> str:
    """
    Identifica a un cliente existente por su teléfono.
    Si lo encuentra, queda identificado para el resto de la conversación.

    Args:
        telefono: Teléfono del cliente.
    """
    cliente = buscar_cliente_por_telefono(telefono)

    if cliente is None:
        return "No se ha encontrado ningún cliente con ese teléfono."

    sesion.guardar_cliente(config, cliente["id_cliente"])

    return f"Cliente encontrado y identificado. Nombre: {cliente['nombre']}."


@tool
def registrar_cliente(
    nombre: str,
    telefono: str,
    config: RunnableConfig,
    email: str = "",
) -> str:
    """
    Registra a un cliente nuevo (o lo identifica si el teléfono ya existía).
    Queda identificado para el resto de la conversación.

    Args:
        nombre: Nombre del cliente.
        telefono: Teléfono del cliente.
        email: Email, solo si el cliente lo ha dado por su cuenta.
    """
    try:
        id_cliente = buscar_o_crear_cliente(
            nombre=nombre,
            telefono=telefono,
            email=email,
        )
    except ValueError as error:
        return f"No se ha podido registrar el cliente: {error}"

    sesion.guardar_cliente(config, id_cliente)

    return "Cliente registrado e identificado correctamente."


# ============================================================
# CITAS DEL CLIENTE IDENTIFICADO
# ============================================================

@tool
def reservar_cita(
    id_servicio: int,
    fecha: str,
    hora_inicio: str,
    config: RunnableConfig,
    profesional: str = "",
) -> str:
    """
    Reserva una cita para el cliente identificado. Antes de crearla se
    comprueba que el horario siga disponible.

    Args:
        id_servicio: ID del servicio que quiere reservar.
        fecha: Fecha de la cita en formato YYYY-MM-DD.
        hora_inicio: Hora de inicio en formato HH:MM.
        profesional: Nombre de la profesional, SOLO si el cliente la ha pedido.
    """
    id_cliente = sesion.cliente_actual(config)

    if id_cliente is None:
        return SIN_CLIENTE

    id_empleado, error = _resolver_profesional(profesional)

    if error:
        return error

    try:
        id_cita = crear_cita(
            id_cliente=id_cliente,
            id_servicio=id_servicio,
            fecha=fecha,
            hora_inicio=hora_inicio,
            id_empleado=id_empleado,
        )
    except ValueError as error:
        return f"No se ha podido realizar la reserva: {error}"

    citas = cargar_citas()
    fila = citas[citas["id_cita"] == id_cita].iloc[0]

    return (
        f"Reserva realizada correctamente. Número de cita {id_cita}, "
        f"atendida por {nombre_empleado(fila['id_empleado'])}."
    )


@tool
def cancelar_cita_tool(id_cita: int, config: RunnableConfig) -> str:
    """
    Cancela una cita futura del cliente identificado.
    La cita no se elimina: su estado pasa a 'cancelada'.

    Args:
        id_cita: ID de la cita que se quiere cancelar.
    """
    id_cliente = sesion.cliente_actual(config)

    if id_cliente is None:
        return SIN_CLIENTE

    try:
        cancelar_cita(id_cita=id_cita, id_cliente=id_cliente)
    except ValueError as error:
        return f"No se ha podido cancelar la cita: {error}"

    return f"La cita {id_cita} ha sido cancelada correctamente."


@tool
def modificar_cita_tool(
    id_cita: int,
    nueva_fecha: str,
    nueva_hora_inicio: str,
    config: RunnableConfig,
) -> str:
    """
    Cambia la fecha y la hora de una cita futura del cliente identificado.
    Mantiene el mismo servicio. Antes se comprueba que el nuevo horario esté libre.

    Args:
        id_cita: ID de la cita que se quiere modificar.
        nueva_fecha: Nueva fecha en formato YYYY-MM-DD.
        nueva_hora_inicio: Nueva hora de inicio en formato HH:MM.
    """
    id_cliente = sesion.cliente_actual(config)

    if id_cliente is None:
        return SIN_CLIENTE

    try:
        modificar_cita(
            id_cita=id_cita,
            id_cliente=id_cliente,
            nueva_fecha=nueva_fecha,
            nueva_hora_inicio=nueva_hora_inicio,
        )
    except ValueError as error:
        return f"No se ha podido modificar la cita: {error}"

    return (
        f"La cita {id_cita} ha sido modificada correctamente. "
        f"Nueva fecha: {nueva_fecha}. Nueva hora: {nueva_hora_inicio}."
    )


@tool
def consultar_mis_citas(config: RunnableConfig) -> str:
    """
    Consulta todas las citas del cliente identificado, futuras y pasadas.
    Las canceladas también aparecen para conservar el historial.
    """
    id_cliente = sesion.cliente_actual(config)

    if id_cliente is None:
        return SIN_CLIENTE

    citas = cargar_citas()
    servicios = cargar_servicios()

    citas_cliente = citas[citas["id_cliente"] == id_cliente].copy()

    if citas_cliente.empty:
        return "El cliente no tiene ninguna cita registrada."

    citas_cliente = citas_cliente.merge(
        servicios[["id_servicio", "nombre", "precio"]],
        on="id_servicio",
        how="left",
    )

    citas_cliente["fecha"] = pd.to_datetime(citas_cliente["fecha"])
    citas_cliente = citas_cliente.sort_values(["fecha", "hora_inicio"])

    lineas = []

    for _, cita in citas_cliente.iterrows():
        profesional = (
            "" if pd.isna(cita.get("id_empleado"))
            else f" | con {nombre_empleado(cita['id_empleado'])}"
        )

        lineas.append(
            f"Cita {int(cita['id_cita'])}: {cita['nombre']} | "
            f"{cita['fecha'].strftime('%d/%m/%Y')} | "
            f"{cita['hora_inicio']}-{cita['hora_fin']}{profesional} | "
            f"{float(cita['precio']):.2f} € | Estado: {cita['estado']}"
        )

    return "\n".join(lineas)
