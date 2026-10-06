"""
Huecos bloqueados por el personal (descansos, vacaciones, gestiones...).

Un bloqueo quita disponibilidad solo a la profesional que lo pone:
si Alba bloquea de 14:00 a 15:00, Marta sigue pudiendo recibir citas a esa hora.
"""

import pandas as pd

from reservas import calendario, config, db
from reservas.disponibilidad import hora_a_minutos


def crear_bloqueo(id_empleado, fecha, hora_inicio, hora_fin, motivo=""):
    fecha = pd.to_datetime(fecha).date()

    if hora_a_minutos(hora_fin) <= hora_a_minutos(hora_inicio):
        raise ValueError("La hora de fin tiene que ser posterior a la de inicio.")

    if fecha < config.ahora().date():
        raise ValueError("No se puede bloquear un día que ya ha pasado.")

    inicio = hora_a_minutos(hora_inicio)
    fin = hora_a_minutos(hora_fin)

    with db.transaccion() as con:
        citas = con.execute(
            "SELECT id_cita, hora_inicio, hora_fin FROM citas "
            "WHERE fecha = ? AND id_empleado = ? AND estado = 'confirmada'",
            (str(fecha), int(id_empleado)),
        ).fetchall()

        # No se crean bloqueos encima de citas ya confirmadas: primero hay que cancelarlas.
        solapadas = [
            f"{c['hora_inicio']}-{c['hora_fin']}"
            for c in citas
            if inicio < hora_a_minutos(c["hora_fin"])
            and fin > hora_a_minutos(c["hora_inicio"])
        ]

        if solapadas:
            raise ValueError(
                "Hay citas confirmadas en ese tramo (" + ", ".join(solapadas)
                + "). Cancélalas o muévelas antes de bloquear."
            )

        cursor = con.execute(
            "INSERT INTO bloqueos (id_empleado, fecha, hora_inicio, hora_fin, motivo) "
            "VALUES (?, ?, ?, ?, ?)",
            (int(id_empleado), str(fecha), hora_inicio, hora_fin, (motivo or "").strip()),
        )

        id_bloqueo = int(cursor.lastrowid)

    calendario.solicitar_sincronizacion()

    return id_bloqueo


def bloquear_dia_completo(id_empleado, fecha, motivo=""):
    horario = config.HORARIOS_NEGOCIO.get(pd.to_datetime(fecha).weekday())

    if horario is None:
        raise ValueError("Ese día la peluquería está cerrada.")

    return crear_bloqueo(id_empleado, fecha, horario[0], horario[1], motivo)


def eliminar_bloqueo(id_bloqueo):
    with db.transaccion() as con:
        cursor = con.execute(
            "DELETE FROM bloqueos WHERE id_bloqueo = ?", (int(id_bloqueo),)
        )

        if cursor.rowcount == 0:
            raise ValueError("El bloqueo no existe.")

    calendario.solicitar_sincronizacion()


def listar_bloqueos(fecha):
    fecha = pd.to_datetime(fecha).date().isoformat()

    return db.leer(
        "SELECT * FROM bloqueos WHERE fecha = ? ORDER BY hora_inicio", (fecha,)
    )
