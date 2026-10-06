from pathlib import Path

import pandas as pd
import streamlit as st

from reservas.disponibilidad import (
    buscar_horarios_disponibles,
    obtener_dias_disponibles,
)
from reservas.citas import crear_cita
from reservas.clientes import buscar_o_crear_cliente


# ============================================================
# RUTAS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "datos_negocio"


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="Studio Alba",
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
        padding: 30px 0 25px 0;
    }

    .hero h1 {
        font-size: 42px;
        margin-bottom: 10px;
    }

    .hero p {
        font-size: 18px;
        color: #666;
    }

    .service-card {
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #e5e5e5;
        margin-bottom: 20px;
    }

    .info {
        padding: 15px;
        border-radius: 12px;
        background: #f7f7f7;
        margin: 15px 0;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CARGAR SERVICIOS
# ============================================================

@st.cache_data
def cargar_servicios():

    return pd.read_csv(
        DATA_DIR / "servicios.csv"
    )


servicios = cargar_servicios()


# ============================================================
# CABECERA
# ============================================================

st.markdown(
    """
    <div class="hero">

        <h1>Studio Alba</h1>

        <p>
            Reserva tu cita de forma rápida y sencilla
        </p>

    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# PASO 1 — SERVICIO
# ============================================================

st.header("1. Selecciona un servicio")


servicio_seleccionado = st.selectbox(
    "Servicio",
    servicios["nombre"].tolist(),
)


servicio = servicios[
    servicios["nombre"] == servicio_seleccionado
].iloc[0]


id_servicio = int(
    servicio["id_servicio"]
)

precio = float(
    servicio["precio"]
)

duracion = int(
    servicio["duracion_minutos"]
)


horas = duracion // 60
minutos = duracion % 60


if horas > 0 and minutos > 0:
    duracion_texto = (
        f"{horas} h {minutos} min"
    )
elif horas > 0:
    duracion_texto = (
        f"{horas} h"
    )
else:
    duracion_texto = (
        f"{minutos} min"
    )


st.markdown(
    f"""
    <div class="info">

    <strong>{servicio_seleccionado}</strong>

    <br><br>

    Precio: {precio:.2f} €

    <br>

    Duración: {duracion_texto}

    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# PASO 2 — DÍA
# ============================================================

st.header("2. Selecciona un día")


dias_disponibles = obtener_dias_disponibles(
    id_servicio=id_servicio,
    fecha_inicio=pd.Timestamp.today(),
    numero_dias=60,
)


if not dias_disponibles:

    st.warning(
        "No hay días disponibles para este servicio."
    )

    st.stop()


dias_disponibles = [
    pd.Timestamp(dia)
    for dia in dias_disponibles
]


fecha_seleccionada = st.date_input(
    "Fecha",
    value=dias_disponibles[0].date(),
    min_value=dias_disponibles[0].date(),
)


fecha_timestamp = pd.Timestamp(
    fecha_seleccionada
)


if fecha_timestamp not in dias_disponibles:

    st.warning(
        "Este día no tiene horarios disponibles "
        "para el servicio seleccionado."
    )

    st.stop()


# ============================================================
# PASO 3 — HORA
# ============================================================

st.header("3. Selecciona una hora")


horarios_disponibles = buscar_horarios_disponibles(
    id_servicio=id_servicio,
    fecha=fecha_seleccionada,
)


if not horarios_disponibles:

    st.warning(
        "No quedan horarios disponibles "
        "para este día."
    )

    st.stop()


hora_seleccionada = st.radio(
    "Horas disponibles",
    horarios_disponibles,
    horizontal=True,
)


# ============================================================
# PASO 4 — DATOS DEL CLIENTE
# ============================================================

st.header("4. Tus datos")


nombre = st.text_input(
    "Nombre"
)

telefono = st.text_input(
    "Teléfono"
)

email = st.text_input(
    "Email"
)


# ============================================================
# PASO 5 — CONFIRMAR
# ============================================================

st.header("5. Confirmar reserva")


st.markdown(
    f"""
    <div class="info">

    <strong>Resumen de la reserva</strong>

    <br><br>

    Servicio: {servicio_seleccionado}

    <br>

    Fecha: {fecha_seleccionada.strftime("%d/%m/%Y")}

    <br>

    Hora: {hora_seleccionada}

    <br>

    Duración: {duracion_texto}

    <br>

    Precio: {precio:.2f} €

    </div>
    """,
    unsafe_allow_html=True,
)


if st.button(
    "Confirmar reserva",
    type="primary",
    use_container_width=True,
):
    if not nombre.strip():
        st.error("Introduce tu nombre.")
        st.stop()

    if not telefono.strip():
        st.error("Introduce tu teléfono.")
        st.stop()

    if not email.strip():
        st.error("Introduce tu email.")
        st.stop()

    try:
        id_cliente = buscar_o_crear_cliente(
            nombre=nombre,
            telefono=telefono,
            email=email,
        )

        st.write("ID CLIENTE:", id_cliente)

        id_cita = crear_cita(
            id_cliente=id_cliente,
            id_servicio=id_servicio,
            fecha=fecha_seleccionada,
            hora_inicio=hora_seleccionada,
        )

        st.success(
            f"¡Reserva confirmada! Tu número de cita es {id_cita}."
        )

    except ValueError as error:
        st.error(str(error))

    except Exception as error:
        st.error("No se ha podido crear la reserva.")
        st.exception(error)