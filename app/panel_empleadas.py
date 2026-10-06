"""
Agenda de Studio Alba para el personal.

Permite ver el día de cada profesional, apuntar citas que entran por teléfono
o en la tienda, cancelar citas y bloquear huecos. Todo se guarda en la misma
base de datos que usa el asistente, así que el asistente deja de ofrecer
inmediatamente cualquier hueco que se ocupe o se bloquee aquí.

Arranque:
    poetry run streamlit run app/panel_empleadas.py

Acceso: define PANEL_PIN en el .env. Sin PIN el panel no se abre.
"""

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from reservas import calendario, config
from reservas.bloqueos import (
    bloquear_dia_completo,
    crear_bloqueo,
    eliminar_bloqueo,
)
from reservas.citas import cancelar_cita_como_empleada, crear_cita
from reservas.clientes import (
    buscar_cliente_por_telefono,
    buscar_o_crear_cliente,
    cargar_clientes,
    normalizar_telefono,
)
from reservas.disponibilidad import (
    buscar_horarios_disponibles,
    cargar_empleados,
    cargar_servicios,
    hora_a_minutos,
    minutos_a_hora,
    obtener_bloqueos_del_dia,
    obtener_citas_del_dia,
)

load_dotenv()

st.set_page_config(
    page_title="Studio Alba · Agenda",
    page_icon="✦",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Bodoni+Moda:ital,opsz,wght@0,6..96,400&family=Jost:wght@300;400;500&display=swap');

    .stApp { background: #eeece6; font-family: 'Jost', 'Helvetica Neue', Arial, sans-serif; }
    .block-container { max-width: 900px; padding-top: 2rem; }
    #MainMenu, footer, header { visibility: hidden; }

    h1, h2, h3 { font-family: 'Bodoni Moda', Georgia, serif !important; font-weight: 400 !important; color: #17231d; }

    div.stButton > button {
        background: #17231d; color: #f8f7f3; border: none; border-radius: 4px;
        padding: 0.6rem 1.4rem; font-family: 'Jost', sans-serif;
    }
    div.stButton > button:hover { background: #24382e; color: #f8f7f3; }
    div.stButton > button:focus-visible { outline: 2px solid #a8895a; outline-offset: 2px; }

    .hueco { border-left: 2px solid #a8895a; padding: 0.15rem 0 0.15rem 0.7rem; margin-bottom: 0.7rem; line-height: 1.4; }
    .hueco small { color: #6f736c; }
    .bloqueo { border-left-color: #6f736c; color: #6f736c; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# ACCESO
# ============================================================

PIN = os.getenv("PANEL_PIN", "").strip()

if not PIN:
    st.error(
        "El panel está desactivado. Añade PANEL_PIN al archivo .env "
        "y vuelve a arrancarlo."
    )
    st.stop()

if not st.session_state.get("acceso"):
    st.title("Agenda")
    pin_introducido = st.text_input("PIN de acceso", type="password")

    if st.button("Entrar"):
        if pin_introducido == PIN:
            st.session_state.acceso = True
            st.rerun()
        else:
            st.error("PIN incorrecto.")

    st.stop()


# ============================================================
# AYUDAS
# ============================================================

ORIGEN_ETIQUETAS = {
    "asistente": "web",
    "telefono": "teléfono",
    "tienda": "tienda",
}


def horas_del_dia(fecha, paso=15):
    """Horas del día en tramos de 15 minutos, dentro del horario de apertura."""
    horario = config.HORARIOS_NEGOCIO.get(pd.to_datetime(fecha).weekday())

    if horario is None:
        return []

    return [
        minutos_a_hora(m)
        for m in range(hora_a_minutos(horario[0]), hora_a_minutos(horario[1]) + 1, paso)
    ]


def fecha_bonita(fecha):
    return pd.to_datetime(fecha).strftime("%d/%m/%Y")


empleados = cargar_empleados()
nombres = {int(r["id_empleado"]): str(r["nombre"]) for _, r in empleados.iterrows()}

servicios = cargar_servicios()
nombre_servicio = {int(r["id_servicio"]): str(r["nombre"]) for _, r in servicios.iterrows()}

hoy = config.ahora().date()

# Mensaje que sobrevive al rerun tras guardar algo.
if "aviso" in st.session_state:
    st.success(st.session_state.pop("aviso"))

st.title("Agenda")

tab_agenda, tab_cita, tab_bloqueo = st.tabs(["Agenda del día", "Nueva cita", "Bloquear hueco"])


# ============================================================
# AGENDA DEL DÍA
# ============================================================

with tab_agenda:
    fecha = st.date_input("Día", value=hoy, format="DD/MM/YYYY", key="agenda_fecha")

    citas = obtener_citas_del_dia(fecha)
    bloqueos = obtener_bloqueos_del_dia(fecha)
    clientes = cargar_clientes().set_index("id_cliente")

    if config.HORARIOS_NEGOCIO.get(pd.to_datetime(fecha).weekday()) is None:
        st.info("La peluquería está cerrada este día.")

    columnas = st.columns(len(nombres))

    for columna, (id_empleado, nombre) in zip(columnas, nombres.items()):
        with columna:
            st.subheader(nombre)

            filas = []

            for _, c in citas[citas["id_empleado"] == id_empleado].iterrows():
                cliente = clientes.loc[c["id_cliente"]] if c["id_cliente"] in clientes.index else None
                filas.append((
                    c["hora_inicio"],
                    f"<div class='hueco'><b>{c['hora_inicio']}–{c['hora_fin']}</b> "
                    f"{cliente['nombre'] if cliente is not None else 'Cliente'}<br>"
                    f"<small>{nombre_servicio.get(int(c['id_servicio']), 'Servicio')} · "
                    f"{ORIGEN_ETIQUETAS.get(c['origen'], c['origen'])}</small></div>",
                ))

            for _, b in bloqueos[bloqueos["id_empleado"] == id_empleado].iterrows():
                filas.append((
                    b["hora_inicio"],
                    f"<div class='hueco bloqueo'><b>{b['hora_inicio']}–{b['hora_fin']}</b> "
                    f"Bloqueado<br><small>{b['motivo'] or 'Sin motivo'}</small></div>",
                ))

            if not filas:
                st.caption("Sin citas ni bloqueos.")

            for _, html in sorted(filas):
                st.markdown(html, unsafe_allow_html=True)

    st.divider()

    with st.expander("Cancelar una cita"):
        if citas.empty:
            st.caption("No hay citas confirmadas este día.")
        else:
            opciones = {}
            for _, c in citas.sort_values("hora_inicio").iterrows():
                cliente = clientes.loc[c["id_cliente"]] if c["id_cliente"] in clientes.index else None
                telefono = cliente["telefono"] if cliente is not None else ""
                etiqueta = (
                    f"{c['hora_inicio']} · {nombres.get(int(c['id_empleado']), '?')} · "
                    f"{cliente['nombre'] if cliente is not None else 'Cliente'} ({telefono})"
                )
                opciones[etiqueta] = int(c["id_cita"])

            elegida = st.selectbox("Cita", list(opciones), key="cancelar_cita")

            if st.button("Cancelar cita", key="boton_cancelar"):
                try:
                    cancelar_cita_como_empleada(opciones[elegida])
                    st.session_state.aviso = "Cita cancelada. El hueco vuelve a estar libre."
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))

    with st.expander("Quitar un bloqueo"):
        if bloqueos.empty:
            st.caption("No hay bloqueos este día.")
        else:
            opciones = {
                f"{b['hora_inicio']}–{b['hora_fin']} · {nombres.get(int(b['id_empleado']), '?')}"
                f" · {b['motivo'] or 'Sin motivo'}": int(b["id_bloqueo"])
                for _, b in bloqueos.sort_values("hora_inicio").iterrows()
            }

            elegido = st.selectbox("Bloqueo", list(opciones), key="quitar_bloqueo")

            if st.button("Quitar bloqueo", key="boton_quitar"):
                try:
                    eliminar_bloqueo(opciones[elegido])
                    st.session_state.aviso = "Bloqueo eliminado."
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))


    st.divider()

    if calendario.habilitado():
        st.caption(
            "Google Calendar conectado: las citas y los bloqueos se reflejan solos en el "
            "calendario de cada profesional. Lo que se escriba a mano allí no bloquea huecos."
        )

        if st.button("Sincronizar ahora", key="sync_ahora"):
            with st.spinner("Sincronizando…"):
                resumen = calendario.sincronizar()

            if resumen["errores"]:
                st.error("Hubo errores: " + " | ".join(resumen["errores"][:3]))
            else:
                st.success(
                    f"Calendarios al día: {resumen['creados']} nuevas, "
                    f"{resumen['actualizados']} cambiadas, {resumen['borrados']} eliminadas."
                )
    else:
        st.caption("Google Calendar sin configurar.")


# ============================================================
# NUEVA CITA (teléfono o tienda)
# ============================================================

with tab_cita:
    # El contador cambia las claves de los campos: así se vacían tras guardar.
    n = st.session_state.get("n_cita", 0)

    telefono = st.text_input("Teléfono del cliente", key=f"cita_tel_{n}")

    cliente = buscar_cliente_por_telefono(telefono) if normalizar_telefono(telefono) else None
    nombre_nuevo = ""

    if cliente:
        st.success(f"Cliente registrado: {cliente['nombre']}")
    elif normalizar_telefono(telefono):
        nombre_nuevo = st.text_input("Nombre (cliente nuevo)", key=f"cita_nombre_{n}")

    servicio = st.selectbox(
        "Servicio",
        list(nombre_servicio),
        format_func=lambda i: (
            f"{nombre_servicio[i]} · "
            f"{int(servicios.loc[servicios['id_servicio'] == i, 'duracion_minutos'].iloc[0])} min"
        ),
        key=f"cita_servicio_{n}",
    )

    col_prof, col_fecha = st.columns(2)

    with col_prof:
        profesional = st.selectbox(
            "Profesional",
            [None] + list(nombres),
            format_func=lambda i: "Cualquiera" if i is None else nombres[i],
            key=f"cita_prof_{n}",
        )

    with col_fecha:
        fecha_cita = st.date_input(
            "Día", value=hoy, min_value=hoy, format="DD/MM/YYYY", key=f"cita_fecha_{n}"
        )

    horas = buscar_horarios_disponibles(
        id_servicio=servicio,
        fecha=fecha_cita,
        intervalo=15,
        id_empleado=profesional,
        desde_hora_actual=False,
    )

    col_hora, col_origen = st.columns(2)

    with col_hora:
        hora = st.selectbox("Hora", horas, key=f"cita_hora_{n}") if horas else None
        if not horas:
            st.warning("No hay huecos libres ese día para esa profesional.")

    with col_origen:
        origen = st.radio(
            "Cómo ha llegado",
            ["telefono", "tienda"],
            format_func=lambda o: "Por teléfono" if o == "telefono" else "En la tienda",
            key=f"cita_origen_{n}",
        )

    if st.button("Guardar cita", key=f"cita_guardar_{n}", disabled=hora is None):
        if not normalizar_telefono(telefono):
            st.error("Escribe el teléfono del cliente.")
        elif not cliente and not nombre_nuevo.strip():
            st.error("Es un cliente nuevo: escribe su nombre.")
        else:
            try:
                id_cliente = (
                    cliente["id_cliente"] if cliente
                    else buscar_o_crear_cliente(nombre_nuevo, telefono)
                )

                id_cita = crear_cita(
                    id_cliente=id_cliente,
                    id_servicio=servicio,
                    fecha=fecha_cita,
                    hora_inicio=hora,
                    id_empleado=profesional,
                    origen=origen,
                    intervalo=15,
                    desde_hora_actual=False,
                )

                citas_guardadas = obtener_citas_del_dia(fecha_cita)
                asignada = int(
                    citas_guardadas.loc[citas_guardadas["id_cita"] == id_cita, "id_empleado"].iloc[0]
                )

                st.session_state.aviso = (
                    f"Cita guardada: {fecha_bonita(fecha_cita)} a las {hora} con {nombres[asignada]}."
                )
                st.session_state.n_cita = n + 1
                st.rerun()

            except ValueError as error:
                st.error(str(error))


# ============================================================
# BLOQUEAR HUECO
# ============================================================

with tab_bloqueo:
    m = st.session_state.get("n_bloqueo", 0)

    profesional_b = st.selectbox(
        "Profesional",
        list(nombres),
        format_func=lambda i: nombres[i],
        key=f"bloq_prof_{m}",
    )

    fecha_b = st.date_input(
        "Día", value=hoy, min_value=hoy, format="DD/MM/YYYY", key=f"bloq_fecha_{m}"
    )

    todo_el_dia = st.checkbox("Todo el día (vacaciones, día libre)", key=f"bloq_dia_{m}")

    opciones_horas = horas_del_dia(fecha_b)

    if not opciones_horas:
        st.info("La peluquería está cerrada ese día.")
    elif not todo_el_dia:
        col_i, col_f = st.columns(2)

        with col_i:
            hora_i = st.selectbox("Desde", opciones_horas[:-1], key=f"bloq_ini_{m}")

        with col_f:
            posibles_fin = [h for h in opciones_horas if h > hora_i]
            hora_f = st.selectbox("Hasta", posibles_fin, key=f"bloq_fin_{m}")

    motivo = st.text_input("Motivo (opcional)", key=f"bloq_motivo_{m}")

    if st.button("Bloquear", key=f"bloq_guardar_{m}", disabled=not opciones_horas):
        try:
            if todo_el_dia:
                bloquear_dia_completo(profesional_b, fecha_b, motivo)
                resumen = "todo el día"
            else:
                crear_bloqueo(profesional_b, fecha_b, hora_i, hora_f, motivo)
                resumen = f"de {hora_i} a {hora_f}"

            st.session_state.aviso = (
                f"{nombres[profesional_b]} bloqueada {resumen} el {fecha_bonita(fecha_b)}."
            )
            st.session_state.n_bloqueo = m + 1
            st.rerun()

        except ValueError as error:
            st.error(str(error))
