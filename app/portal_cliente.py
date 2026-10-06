from pathlib import Path
from datetime import datetime
from reservas.citas import (
    cancelar_cita,
    modificar_cita,
)

from reservas.disponibilidad import (
    buscar_horarios_disponibles,
    obtener_dias_disponibles,
)

import pandas as pd
import streamlit as st


# ============================================================
# RUTAS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "datos_negocio"


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="Mi cuenta - Studio Alba",
    page_icon="✦",
    layout="centered",
)


# ============================================================
# ESTILOS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        max-width: 900px;
        padding-top: 3rem;
        padding-bottom: 4rem;
    }

    .hero {
        text-align: center;
        padding: 20px 0 35px 0;
    }

    .hero h1 {
        font-size: 42px;
        margin-bottom: 8px;
    }

    .hero p {
        font-size: 18px;
        color: #666;
    }

    .appointment-card {
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #e5e5e5;
        margin-bottom: 15px;
    }

    .appointment-date {
        font-size: 22px;
        font-weight: 600;
        margin-bottom: 10px;
    }

    .appointment-service {
        font-size: 18px;
        margin-bottom: 8px;
    }

    .appointment-info {
        color: #666;
        line-height: 1.7;
    }

    .section-title {
        margin-top: 30px;
        margin-bottom: 20px;
    }

    .empty {
        padding: 25px;
        border-radius: 15px;
        background: #f7f7f7;
        text-align: center;
        color: #666;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CARGAR DATOS
# ============================================================

# Clientes y citas cambian con cada reserva: vienen de SQLite y sin caché.
from reservas.clientes import cargar_clientes  # noqa: E402
from reservas.disponibilidad import cargar_citas  # noqa: E402


@st.cache_data
def cargar_servicios():
    return pd.read_csv(DATA_DIR / "servicios.csv")


# ============================================================
# FUNCIONES
# ============================================================

def buscar_cliente(telefono, email):
    clientes = cargar_clientes()

    telefono = telefono.strip()
    email = email.strip().lower()

    clientes_encontrados = clientes[
        (
            clientes["telefono"]
            .astype(str)
            .str.strip()
            == telefono
        )
        |
        (
            clientes["email"]
            .astype(str)
            .str.strip()
            .str.lower()
            == email
        )
    ]

    if clientes_encontrados.empty:
        return None

    return clientes_encontrados.iloc[0]


def obtener_citas_cliente(id_cliente):
    citas = cargar_citas()

    citas_cliente = citas[
    citas["id_cliente"] == id_cliente
    ].copy()

    if citas_cliente.empty:
        return citas_cliente

    citas_cliente["fecha"] = pd.to_datetime(
        citas_cliente["fecha"]
    )

    return citas_cliente


def añadir_nombre_servicio(citas):
    servicios = cargar_servicios()

    citas = citas.merge(
        servicios[
            [
                "id_servicio",
                "nombre",
                "precio",
                "duracion_minutos",
            ]
        ],
        on="id_servicio",
        how="left",
    )

    return citas


def es_cita_futura(cita):
    fecha_hora = datetime.combine(
        cita["fecha"].date(),
        datetime.strptime(
            cita["hora_inicio"],
            "%H:%M"
        ).time(),
    )

    return fecha_hora >= datetime.now()


# ============================================================
# CABECERA
# ============================================================

st.markdown(
    """
    <div class="hero">
        <h1>Studio Alba</h1>
        <p>Mi cuenta</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# IDENTIFICACIÓN
# ============================================================

st.header("Accede a tus citas")

st.write(
    "Introduce el teléfono y el email utilizados al realizar tu reserva."
)

telefono = st.text_input(
    "Teléfono",
    placeholder="Ej. 618275050",
)

email = st.text_input(
    "Email",
    placeholder="Ej. nombre@email.com",
)


if st.button(
    "Ver mis citas",
    type="primary",
    use_container_width=True,
):

    if not telefono.strip():
        st.error("Introduce tu teléfono.")
        st.stop()

    if not email.strip():
        st.error("Introduce tu email.")
        st.stop()

    cliente = buscar_cliente(
        telefono=telefono,
        email=email,
    )

    if cliente is None:
        st.error(
            "No hemos encontrado ningún cliente con esos datos."
        )
        st.stop()

    st.session_state["cliente"] = cliente.to_dict()


# ============================================================
# MOSTRAR PORTAL
# ============================================================

if "cliente" in st.session_state:

    cliente = st.session_state["cliente"]

    id_cliente = int(cliente["id_cliente"])
    nombre = cliente["nombre"]

    st.divider()

    st.subheader(f"Hola, {nombre} 👋")

    citas = obtener_citas_cliente(id_cliente)

    if citas.empty:

        st.markdown(
            """
            <div class="empty">
                No tienes ninguna cita registrada.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.stop()

    citas = añadir_nombre_servicio(citas)

    # --------------------------------------------------------
    # SEPARAR FUTURAS Y PASADAS
    # --------------------------------------------------------

    citas_futuras = []
    citas_pasadas = []

    for _, cita in citas.iterrows():

        if (
            es_cita_futura(cita)
            and cita["estado"] == "confirmada"
        ):
            citas_futuras.append(cita)
        else:
            citas_pasadas.append(cita)

    citas_futuras = sorted(
        citas_futuras,
        key=lambda x: (
            x["fecha"],
            x["hora_inicio"],
        ),
    )

    citas_pasadas = sorted(
        citas_pasadas,
        key=lambda x: (
            x["fecha"],
            x["hora_inicio"],
        ),
        reverse=True,
    )

    # ========================================================
    # PRÓXIMAS CITAS
    # ========================================================

    st.markdown(
        '<h2 class="section-title">📅 Próximas citas</h2>',
        unsafe_allow_html=True,
    )

    if not citas_futuras:

        st.markdown(
            """
            <div class="empty">
                No tienes próximas citas.
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:

        for cita in citas_futuras:

            fecha = cita["fecha"].strftime("%d/%m/%Y")
            id_cita = int(cita["id_cita"])
            id_servicio = int(cita["id_servicio"])

            with st.container(border=True):

                st.subheader(cita["nombre"])

                st.write(f"📅 {fecha}")

                st.write(
                    f"🕐 {cita['hora_inicio']} - {cita['hora_fin']}"
                )

                st.write(
                    f"💶 {float(cita['precio']):.2f} €"
                )

                st.write(
                    f"Estado: {cita['estado']}"
                )

                # -----------------------------------------
                # MODIFICAR
                # -----------------------------------------

                if st.button(
                    "Modificar cita",
                    key=f"modificar_{id_cita}",
                    use_container_width=True,
                ):
                    st.session_state[
                        f"modificando_{id_cita}"
                    ] = True

                if st.session_state.get(
                    f"modificando_{id_cita}",
                    False,
                ):

                    st.markdown("### Cambiar fecha y hora")

                    dias_disponibles = obtener_dias_disponibles(
                        id_servicio=id_servicio,
                        fecha_inicio=pd.Timestamp.today(),
                        numero_dias=60,
                    )

                    fecha_actual = cita["fecha"].date()

                    if fecha_actual not in dias_disponibles:
                        dias_disponibles.append(fecha_actual)

                    dias_disponibles = sorted(
                        set(dias_disponibles)
                    )

                    nueva_fecha = st.selectbox(
                        "Nueva fecha",
                        dias_disponibles,
                        format_func=lambda fecha: fecha.strftime(
                            "%d/%m/%Y"
                        ),
                        key=f"nueva_fecha_{id_cita}",
                    )

                    horarios_disponibles = (
                        buscar_horarios_disponibles(
                            id_servicio=id_servicio,
                            fecha=nueva_fecha,
                            id_cita_excluir=id_cita,
                        )
                    )

                    if horarios_disponibles:

                        nueva_hora = st.selectbox(
                            "Nueva hora",
                            horarios_disponibles,
                            key=f"nueva_hora_{id_cita}",
                        )

                        if st.button(
                            "Guardar cambios",
                            key=f"guardar_{id_cita}",
                            type="primary",
                            use_container_width=True,
                        ):

                            try:

                                modificar_cita(
                                    id_cita=id_cita,
                                    id_cliente=id_cliente,
                                    nueva_fecha=nueva_fecha,
                                    nueva_hora_inicio=nueva_hora,
                                )

                                st.cache_data.clear()

                                st.session_state[
                                    f"modificando_{id_cita}"
                                ] = False

                                st.success(
                                    "Tu cita se ha modificado correctamente."
                                )

                                st.rerun()

                            except ValueError as error:

                                st.error(str(error))

                    else:

                        st.warning(
                            "No hay horarios disponibles para ese día."
                        )

                # -----------------------------------------
                # CANCELAR
                # -----------------------------------------

                if st.button(
                    "Cancelar cita",
                    key=f"cancelar_{id_cita}",
                    use_container_width=True,
                ):

                    try:

                        cancelar_cita(
                            id_cita=id_cita,
                            id_cliente=id_cliente,
                        )

                        st.cache_data.clear()

                        st.success(
                            "La cita ha sido cancelada."
                        )

                        st.rerun()

                    except ValueError as error:

                        st.error(str(error))

    # ========================================================
    # HISTORIAL
    # ========================================================

    st.markdown(
        '<h2 class="section-title">📖 Historial de citas</h2>',
        unsafe_allow_html=True,
    )

    if not citas_pasadas:

        st.markdown(
            """
            <div class="empty">
                Todavía no tienes citas anteriores.
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:

        for cita in citas_pasadas:

            fecha = cita["fecha"].strftime("%d/%m/%Y")

            with st.container(border=True):

                st.subheader(cita["nombre"])

                st.write(f"📅 {fecha}")
                st.write(
                    f"🕐 {cita['hora_inicio']} - {cita['hora_fin']}"
                )
                st.write(
                    f"💶 {float(cita['precio']):.2f} €"
                )
                st.write(
                    f"Estado: {cita['estado']}"
                )