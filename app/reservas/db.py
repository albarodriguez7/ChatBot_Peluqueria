"""
Base de datos SQLite de Studio Alba.

Guarda lo que cambia con cada reserva: clientes y citas.
Los datos maestros (servicios, empleados) y la contabilidad siguen en CSV,
porque los edita la propietaria y la app solo los lee.

La primera vez que se abre la base de datos vacía, importa
clientes.csv y citas.csv. Después, esos dos CSV ya no se usan.
"""

import sqlite3
from contextlib import contextmanager

import pandas as pd

from reservas import config

ESQUEMA = """
CREATE TABLE IF NOT EXISTS clientes (
    id_cliente      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT    NOT NULL,
    telefono        TEXT    NOT NULL,
    email           TEXT    NOT NULL DEFAULT '',
    fecha_alta      TEXT,
    ultimo_servicio TEXT    NOT NULL DEFAULT '',
    total_visitas   INTEGER NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_clientes_telefono ON clientes(telefono);

CREATE TABLE IF NOT EXISTS citas (
    id_cita     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente  INTEGER NOT NULL REFERENCES clientes(id_cliente),
    id_servicio INTEGER NOT NULL,
    id_empleado INTEGER NOT NULL,
    fecha       TEXT    NOT NULL,
    hora_inicio TEXT    NOT NULL,
    hora_fin    TEXT    NOT NULL,
    estado      TEXT    NOT NULL CHECK (estado IN ('confirmada', 'cancelada')),
    origen      TEXT    NOT NULL DEFAULT 'asistente'   -- asistente | telefono | tienda
);

-- Huecos que una profesional deja sin reservar (descanso, vacaciones, gestiones...).
CREATE TABLE IF NOT EXISTS bloqueos (
    id_bloqueo  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_empleado INTEGER NOT NULL,
    fecha       TEXT    NOT NULL,
    hora_inicio TEXT    NOT NULL,
    hora_fin    TEXT    NOT NULL,
    motivo      TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS ix_bloqueos_fecha ON bloqueos(fecha);

CREATE INDEX IF NOT EXISTS ix_citas_fecha  ON citas(fecha, estado);
CREATE INDEX IF NOT EXISTS ix_citas_cliente ON citas(id_cliente);
"""

_INICIALIZADAS = set()


def ruta_db():
    # Se calcula en cada llamada para que los tests puedan cambiar config.DATA_DIR.
    return config.DATA_DIR / "studio_alba.db"


def _abrir():
    con = sqlite3.connect(ruta_db(), timeout=10, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    return con


def _inicializar():
    ruta = ruta_db()

    if ruta in _INICIALIZADAS and ruta.exists():
        return

    ruta.parent.mkdir(parents=True, exist_ok=True)

    con = _abrir()
    try:
        con.executescript(ESQUEMA)
        _migrar_esquema(con)
        _importar_csv_si_esta_vacia(con)
    finally:
        con.close()

    _INICIALIZADAS.add(ruta)


def conectar():
    _inicializar()
    return _abrir()


@contextmanager
def transaccion():
    """
    Transacción de escritura. BEGIN IMMEDIATE toma el bloqueo de escritura
    desde el principio, así que "comprobar hueco + insertar" es atómico:
    dos reservas a la vez no pueden ocupar el mismo hueco, ni siquiera
    desde dos procesos distintos.
    """
    con = conectar()
    try:
        con.execute("BEGIN IMMEDIATE")
        yield con
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def leer(sql, parametros=()):
    con = conectar()
    try:
        return pd.read_sql_query(sql, con, params=parametros)
    finally:
        con.close()


def _migrar_esquema(con):
    """Añade lo nuevo a bases de datos creadas con versiones anteriores."""
    columnas = [fila[1] for fila in con.execute("PRAGMA table_info(citas)")]

    if "origen" not in columnas:
        con.execute(
            "ALTER TABLE citas ADD COLUMN origen TEXT NOT NULL DEFAULT 'asistente'"
        )


# ============================================================
# IMPORTACIÓN INICIAL DESDE CSV
# ============================================================

def _importar_csv_si_esta_vacia(con):
    from reservas.clientes import normalizar_telefono

    hay_clientes = con.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
    hay_citas = con.execute("SELECT COUNT(*) FROM citas").fetchone()[0]

    if hay_clientes or hay_citas:
        return

    ruta_clientes = config.DATA_DIR / "clientes.csv"
    ruta_citas = config.DATA_DIR / "citas.csv"

    clientes = (
        pd.read_csv(ruta_clientes, encoding="utf-8-sig")
        if ruta_clientes.exists() else pd.DataFrame()
    )

    con.execute("BEGIN")
    try:
        if not clientes.empty:
            clientes["telefono"] = clientes["telefono"].map(normalizar_telefono)

            repetidos = clientes[clientes["telefono"].duplicated(keep=False)]
            if not repetidos.empty:
                raise ValueError(
                    "clientes.csv tiene teléfonos repetidos; corrígelos antes de migrar: "
                    + ", ".join(repetidos["telefono"].unique())
                )

            for _, c in clientes.iterrows():
                con.execute(
                    "INSERT INTO clientes (id_cliente, nombre, telefono, email, fecha_alta, "
                    "ultimo_servicio, total_visitas) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        int(c["id_cliente"]),
                        str(c["nombre"]).strip(),
                        c["telefono"],
                        "" if pd.isna(c.get("email")) else str(c["email"]).strip().lower(),
                        None if pd.isna(c.get("fecha_alta")) else str(c["fecha_alta"]),
                        "" if pd.isna(c.get("ultimo_servicio")) else str(c["ultimo_servicio"]),
                        0 if pd.isna(c.get("total_visitas")) else int(c["total_visitas"]),
                    ),
                )

        if ruta_citas.exists():
            citas = pd.read_csv(ruta_citas, encoding="utf-8-sig")

            if "id_empleado" not in citas.columns:
                citas["id_empleado"] = None

            # Citas de clientes que no existen: no se importan, se guardan aparte.
            ids_validos = {
                r[0] for r in con.execute("SELECT id_cliente FROM clientes")
            }
            huerfanas = citas[~citas["id_cliente"].isin(ids_validos)]

            if not huerfanas.empty:
                huerfanas.to_csv(
                    config.DATA_DIR / "citas_huerfanas.csv",
                    index=False,
                    encoding="utf-8",
                )
                citas = citas[citas["id_cliente"].isin(ids_validos)]

            for _, c in citas.iterrows():
                # Sin profesional asignada: reparto alterno entre Alba (1) y Marta (2).
                if pd.isna(c["id_empleado"]):
                    empleado = 1 if int(c["id_cita"]) % 2 else 2
                else:
                    empleado = int(c["id_empleado"])
                con.execute(
                    "INSERT INTO citas (id_cita, id_cliente, id_servicio, id_empleado, "
                    "fecha, hora_inicio, hora_fin, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        int(c["id_cita"]),
                        int(c["id_cliente"]),
                        int(c["id_servicio"]),
                        empleado,
                        str(c["fecha"]),
                        str(c["hora_inicio"]),
                        str(c["hora_fin"]),
                        str(c["estado"]),
                    ),
                )

        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
