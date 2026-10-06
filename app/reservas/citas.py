import pandas as pd

from reservas import calendario, config, db
from reservas.clientes import existe_cliente
from reservas.disponibilidad import (
    buscar_horarios_disponibles,
    empleados_libres,
    hora_a_minutos,
    minutos_a_hora,
    obtener_bloqueos_del_dia,
    obtener_citas_del_dia,
    obtener_duracion_servicio,
)

ORIGENES = ("asistente", "telefono", "tienda")


def _elegir_empleado(fecha, inicio, fin, id_empleado=None, id_cita_excluir=None):
    """
    Elige quién atiende. Si se pide una profesional concreta, tiene que estar libre.
    Si no, se elige la que tenga menos citas ese día (reparte la carga).
    """
    citas_dia = obtener_citas_del_dia(fecha)
    bloqueos = obtener_bloqueos_del_dia(fecha)

    libres = empleados_libres(citas_dia, inicio, fin, id_cita_excluir, bloqueos)

    if id_empleado is not None:
        if int(id_empleado) not in libres:
            raise ValueError("Esa profesional no está disponible a esa hora.")
        return int(id_empleado)

    if not libres:
        raise ValueError("No hay ninguna profesional disponible a esa hora.")

    def carga(id_emp):
        return int((citas_dia["id_empleado"] == id_emp).sum())

    return min(libres, key=lambda id_emp: (carga(id_emp), id_emp))


def crear_cita(
    id_cliente,
    id_servicio,
    fecha,
    hora_inicio,
    id_empleado=None,
    origen="asistente",
    intervalo=30,
    desde_hora_actual=True,
):
    """
    Crea una cita si el horario sigue disponible y devuelve su id.

    origen: quién la ha creado ("asistente", "telefono" o "tienda").
    intervalo y desde_hora_actual existen para el personal: pueden apuntar
    citas cada 15 minutos y a clientes que ya están en la tienda.

    Comprobar el hueco y escribir ocurren dentro de la misma transacción
    de escritura: dos reservas a la vez no pueden ocupar el mismo hueco.
    """
    if origen not in ORIGENES:
        raise ValueError(f"Origen no válido: {origen}.")

    with db.transaccion() as con:

        if not existe_cliente(id_cliente):
            raise ValueError("El cliente no existe.")

        horarios = buscar_horarios_disponibles(
            id_servicio=id_servicio,
            fecha=fecha,
            intervalo=intervalo,
            id_empleado=id_empleado,
            desde_hora_actual=desde_hora_actual,
        )

        if hora_inicio not in horarios:
            raise ValueError(f"El horario {hora_inicio} ya no está disponible.")

        inicio = hora_a_minutos(hora_inicio)
        fin = inicio + obtener_duracion_servicio(id_servicio)

        empleado = _elegir_empleado(fecha, inicio, fin, id_empleado)

        cursor = con.execute(
            "INSERT INTO citas "
            "(id_cliente, id_servicio, id_empleado, fecha, hora_inicio, hora_fin, "
            "estado, origen) VALUES (?, ?, ?, ?, ?, ?, 'confirmada', ?)",
            (
                int(id_cliente),
                int(id_servicio),
                empleado,
                str(pd.to_datetime(fecha).date()),
                hora_inicio,
                minutos_a_hora(fin),
                origen,
            ),
        )

        id_cita = int(cursor.lastrowid)

    calendario.solicitar_sincronizacion()

    return id_cita


def cancelar_cita_como_empleada(id_cita):
    """
    Cancela cualquier cita futura sin comprobar el cliente.
    SOLO para el panel del personal: el asistente nunca debe llamarla.
    """
    with db.transaccion() as con:
        cita = con.execute(
            "SELECT * FROM citas WHERE id_cita = ?", (int(id_cita),)
        ).fetchone()

        if cita is None:
            raise ValueError("La cita no existe.")

        if cita["estado"] != "confirmada":
            raise ValueError("Esta cita ya estaba cancelada.")

        con.execute(
            "UPDATE citas SET estado = 'cancelada' WHERE id_cita = ?",
            (int(id_cita),),
        )

    calendario.solicitar_sincronizacion()


def _cita_de_cliente(con, id_cita, id_cliente):
    cita = con.execute(
        "SELECT * FROM citas WHERE id_cita = ? AND id_cliente = ?",
        (int(id_cita), int(id_cliente)),
    ).fetchone()

    if cita is None:
        raise ValueError("La cita no existe o no pertenece a este cliente.")

    return cita


def cancelar_cita(id_cita, id_cliente):
    with db.transaccion() as con:
        cita = _cita_de_cliente(con, id_cita, id_cliente)

        if cita["estado"] != "confirmada":
            raise ValueError("Esta cita no se puede cancelar.")

        if pd.to_datetime(cita["fecha"]).date() < config.ahora().date():
            raise ValueError("No puedes cancelar una cita que ya ha pasado.")

        con.execute(
            "UPDATE citas SET estado = 'cancelada' WHERE id_cita = ?",
            (int(id_cita),),
        )

    calendario.solicitar_sincronizacion()


def modificar_cita(
    id_cita,
    id_cliente,
    nueva_fecha,
    nueva_hora_inicio,
):
    with db.transaccion() as con:
        cita = _cita_de_cliente(con, id_cita, id_cliente)

        if cita["estado"] != "confirmada":
            raise ValueError("Esta cita no se puede modificar.")

        if pd.to_datetime(cita["fecha"]).date() < config.ahora().date():
            raise ValueError("No puedes modificar una cita que ya ha pasado.")

        id_servicio = int(cita["id_servicio"])

        horarios = buscar_horarios_disponibles(
            id_servicio=id_servicio,
            fecha=nueva_fecha,
            id_cita_excluir=id_cita,
        )

        if nueva_hora_inicio not in horarios:
            raise ValueError("El nuevo horario ya no está disponible.")

        inicio = hora_a_minutos(nueva_hora_inicio)
        fin = inicio + obtener_duracion_servicio(id_servicio)

        # Se intenta mantener a la misma profesional; si no puede, otra libre.
        try:
            empleado = _elegir_empleado(
                nueva_fecha, inicio, fin, int(cita["id_empleado"]),
                id_cita_excluir=id_cita,
            )
        except ValueError:
            empleado = _elegir_empleado(
                nueva_fecha, inicio, fin, None, id_cita_excluir=id_cita
            )

        con.execute(
            "UPDATE citas SET fecha = ?, hora_inicio = ?, hora_fin = ?, id_empleado = ? "
            "WHERE id_cita = ?",
            (
                str(pd.to_datetime(nueva_fecha).date()),
                nueva_hora_inicio,
                minutos_a_hora(fin),
                empleado,
                int(id_cita),
            ),
        )

    calendario.solicitar_sincronizacion()
