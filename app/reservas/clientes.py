import re

from reservas import config, db


def cargar_clientes():
    return db.leer("SELECT * FROM clientes ORDER BY id_cliente")


def normalizar_telefono(telefono):
    """
    Deja solo los dígitos y quita el prefijo de España.
    '+34 600 10 01 01', '0034600100101' y '600100101' dan el mismo resultado.
    """
    # "600100101.0" aparece si un CSV se ha leído como número decimal.
    digitos = re.sub(r"\D", "", str(telefono).split(".")[0])

    if digitos.startswith("0034"):
        digitos = digitos[4:]
    elif digitos.startswith("34") and len(digitos) > 9:
        digitos = digitos[2:]

    return digitos


def buscar_cliente_por_telefono(telefono):
    """
    Devuelve {'id_cliente': int, 'nombre': str} o None.
    El teléfono es la clave de identificación: hay clientes sin email.
    """
    telefono = normalizar_telefono(telefono)

    if not telefono:
        return None

    con = db.conectar()
    try:
        fila = con.execute(
            "SELECT id_cliente, nombre FROM clientes WHERE telefono = ?",
            (telefono,),
        ).fetchone()
    finally:
        con.close()

    if fila is None:
        return None

    return {"id_cliente": fila["id_cliente"], "nombre": fila["nombre"]}


def existe_cliente(id_cliente):
    con = db.conectar()
    try:
        return con.execute(
            "SELECT 1 FROM clientes WHERE id_cliente = ?", (int(id_cliente),)
        ).fetchone() is not None
    finally:
        con.close()


def buscar_o_crear_cliente(nombre, telefono, email=""):
    nombre = (nombre or "").strip()
    email = (email or "").strip().lower()
    telefono = normalizar_telefono(telefono)

    if not telefono:
        raise ValueError("El teléfono no es válido.")

    with db.transaccion() as con:
        fila = con.execute(
            "SELECT id_cliente FROM clientes WHERE telefono = ?", (telefono,)
        ).fetchone()

        # Si no hay coincidencia por teléfono, se intenta por email
        # (solo cuando se ha indicado uno).
        if fila is None and email:
            fila = con.execute(
                "SELECT id_cliente FROM clientes WHERE email = ?", (email,)
            ).fetchone()

        if fila is not None:
            return int(fila["id_cliente"])

        if not nombre:
            raise ValueError("Falta el nombre para registrar al cliente.")

        cursor = con.execute(
            "INSERT INTO clientes (nombre, telefono, email, fecha_alta) "
            "VALUES (?, ?, ?, ?)",
            (nombre, telefono, email, str(config.ahora().date())),
        )

        return int(cursor.lastrowid)
