import uuid

import streamlit as st

from agent import agent


st.set_page_config(
    page_title="Studio Alba · Peluquería en Madrid",
    page_icon="✦",
    layout="centered",
    initial_sidebar_state="collapsed",
)


# ============================================================
# ESTILOS
# Paleta: bosque #17231d · mármol #eeece6 · marfil #f8f7f3
#         latón #a8895a · tinta #1c1f1c · niebla #6f736c
# Tipografía: Bodoni Moda (títulos) + Jost (texto)
# ============================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Bodoni+Moda:ital,opsz,wght@0,6..96,400;0,6..96,500;1,6..96,400&family=Jost:wght@300;400;500&display=swap');

    :root {
        --bosque: #17231d;
        --marmol: #eeece6;
        --marfil: #f8f7f3;
        --laton: #a8895a;
        --tinta: #1c1f1c;
        --niebla: #6f736c;
        --display: 'Bodoni Moda', 'Didot', 'Bodoni 72', Georgia, serif;
        --texto: 'Jost', 'Futura', 'Helvetica Neue', Arial, sans-serif;
    }

    .stApp {
        background: var(--marmol);
        font-family: var(--texto);
    }

    .block-container {
        max-width: 760px;
        padding-top: 2rem;
        padding-bottom: 6rem;
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }

    /* ---------- Cabecera: marco de espejo ---------- */
    .hero {
        background: var(--bosque);
        padding: 14px;
        margin-bottom: 2.6rem;
    }

    .hero-inner {
        border: 1px solid var(--laton);
        padding: 3.4rem 1.5rem 3rem;
        text-align: center;
    }

    .hero-name {
        font-family: var(--display);
        font-size: clamp(2.6rem, 8vw, 4.2rem);
        font-weight: 400;
        line-height: 1;
        letter-spacing: -0.01em;
        color: var(--marfil);
        margin: 0;
    }

    .hero-sub {
        font-family: var(--texto);
        font-weight: 300;
        font-size: 1rem;
        color: #c9c4b6;
        margin-top: 1rem;
        letter-spacing: 0.04em;
    }

    /* ---------- Introducción ---------- */
    .intro {
        text-align: center;
        margin-bottom: 1.8rem;
    }

    .intro-title {
        font-family: var(--display);
        font-size: 2rem;
        font-weight: 400;
        font-style: italic;
        color: var(--tinta);
        margin-bottom: 0.6rem;
    }

    .intro-text {
        font-family: var(--texto);
        font-weight: 300;
        color: var(--niebla);
        font-size: 1rem;
        line-height: 1.65;
        max-width: 460px;
        margin: 0 auto;
    }

    /* ---------- Chat ---------- */
    [data-testid="stChatMessage"] {
        background: transparent !important;
        border: none !important;
        padding: 0.7rem 0;
        gap: 0;
    }

    [data-testid="stChatMessageAvatarUser"],
    [data-testid="stChatMessageAvatarAssistant"],
    [data-testid="stChatMessage"] > div:first-child:not([data-testid="stChatMessageContent"]) {
        display: none !important;
    }

    [data-testid="stChatMessageContent"] {
        font-family: var(--texto);
        font-size: 1rem;
        line-height: 1.7;
        color: var(--tinta);
    }

    /* Respuestas del asistente: filete de latón a la izquierda */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) [data-testid="stChatMessageContent"] {
        border-left: 1px solid var(--laton);
        padding-left: 1.1rem;
        max-width: 92%;
    }

    /* Mensajes del cliente: alineados a la derecha, sobre bosque */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        flex-direction: row-reverse;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
        display: flex !important;
        align-items: center;
        flex: 0 0 auto !important;
        width: fit-content !important;
        max-width: 80%;
        margin-left: auto;
        background: var(--bosque);
        color: var(--marfil);
        padding: 0.8rem 1.3rem !important;
        border-radius: 4px;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stMarkdownContainer"],
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stMarkdownContainer"] p {
        color: var(--marfil) !important;
        font-family: var(--texto);
        line-height: 1.4;
        margin: 0 !important;
        padding: 0 !important;
    }

    /* ---------- Zona inferior ---------- */
    [data-testid="stBottomBlockContainer"],
    [data-testid="stBottomBlockContainer"] > div,
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div,
    .stChatFloatingInputContainer {
        background: var(--marmol) !important;
    }

    [data-testid="stChatInput"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }

    [data-testid="stChatInput"] > div {
        background: var(--marfil) !important;
        border: 1px solid #c9c4b6 !important;
        border-radius: 4px !important;
        box-shadow: none !important;
    }

    [data-testid="stChatInput"] > div:focus-within {
        border-color: var(--bosque) !important;
    }

    [data-testid="stChatInput"] textarea {
        background: transparent !important;
        color: var(--tinta) !important;
        font-family: var(--texto) !important;
        font-size: 1rem !important;
    }

    [data-testid="stChatInput"] textarea::placeholder {
        color: var(--niebla) !important;
    }

    [data-testid="stChatInput"] button {
        background: var(--bosque) !important;
        color: var(--marfil) !important;
        border-radius: 3px !important;
    }

    /* ---------- Botones de acceso rápido ---------- */
    [class*="st-key-rapido_"],
    .st-key-nueva {
        width: 100% !important;
        display: flex;
        justify-content: center;
    }

    [class*="st-key-rapido_"] .stButton,
    .st-key-nueva .stButton {
        display: flex;
        justify-content: center;
        width: 100%;
    }

    [class*="st-key-rapido_"] button {
        width: 100%;
    }

    div.stButton > button {
        background: transparent;
        color: var(--bosque);
        border: 1px solid var(--bosque);
        border-radius: 4px;
        padding: 0.7rem 0.5rem;
        font-family: var(--texto);
        font-size: 0.95rem;
        font-weight: 400;
        transition: background 0.2s ease, color 0.2s ease;
    }

    div.stButton > button:hover {
        background: var(--bosque);
        color: var(--marfil);
        border-color: var(--bosque);
    }

    div.stButton > button:focus-visible {
        outline: 2px solid var(--laton);
        outline-offset: 2px;
    }

    /* Nueva conversación: enlace discreto */
    div.stButton.stButton > button {
        min-width: 8.5rem;
    }

    .st-key-nueva div.stButton > button {
        border: none !important;
        min-width: 0;
        color: var(--niebla);
        text-decoration: underline;
        text-underline-offset: 4px;
        font-weight: 300;
    }

    .st-key-nueva div.stButton > button:hover {
        background: transparent;
        color: var(--tinta);
    }

    /* ---------- Pie ---------- */
    .footer {
        text-align: center;
        margin-top: 3rem;
        color: var(--niebla);
        font-family: var(--display);
        font-style: italic;
        font-size: 0.95rem;
    }

    @media (max-width: 700px) {
        .block-container {
            padding: 1rem 0.9rem 6rem;
        }

        .hero-inner {
            padding: 2.4rem 1rem 2.2rem;
        }

        .intro-title {
            font-size: 1.7rem;
        }

        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
            max-width: 92%;
        }
    }

    @media (prefers-reduced-motion: reduce) {
        * {
            transition: none !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# ESTADO
# ============================================================

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pendiente" not in st.session_state:
    st.session_state.pendiente = None


def nueva_conversacion():
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.pendiente = None


def enviar_rapido(texto):
    st.session_state.pendiente = texto


def extraer_texto(contenido):
    """Algunos modelos devuelven una lista de bloques en lugar de texto."""
    if isinstance(contenido, list):
        return "".join(
            bloque.get("text", "") if isinstance(bloque, dict) else str(bloque)
            for bloque in contenido
        )
    return contenido


def obtener_respuesta_agente(prompt):
    respuesta = agent.invoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"configurable": {"thread_id": st.session_state.thread_id}},
    )

    return extraer_texto(respuesta["messages"][-1].content)


# ============================================================
# CABECERA
# ============================================================

st.markdown(
    """
    <div class="hero">
        <div class="hero-inner">
            <div class="hero-name">Studio Alba</div>
            <div class="hero-sub">Peluquería en Madrid</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# INTRODUCCIÓN + ACCESOS RÁPIDOS (solo con el chat vacío)
# ============================================================

if not st.session_state.messages:
    st.markdown(
        """
        <div class="intro">
            <div class="intro-title">¿En qué podemos ayudarte?</div>
            <div class="intro-text">
                Reserva una cita, cambia o cancela la que ya tienes,
                o consulta horarios y servicios.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, col1, col2, col3, _ = st.columns([0.3, 1, 1, 1, 0.3])

    with col1:
        st.button(
            "Reservar cita",
            key="rapido_reservar",
            on_click=enviar_rapido,
            args=("Quiero reservar una cita",),
        )

    with col2:
        st.button(
            "Ver horarios",
            key="rapido_horarios",
            on_click=enviar_rapido,
            args=("¿Cuáles son vuestros horarios?",),
        )

    with col3:
        st.button(
            "Mi reserva",
            key="rapido_gestionar",
            on_click=enviar_rapido,
            args=("Quiero gestionar una reserva que ya tengo",),
        )


# ============================================================
# CHAT
# ============================================================

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# ============================================================
# INPUT
# ============================================================

prompt = st.chat_input("Escribe tu mensaje")

if st.session_state.pendiente:
    prompt = st.session_state.pendiente
    st.session_state.pendiente = None


if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Un momento…"):
            try:
                contenido = obtener_respuesta_agente(prompt)

                st.markdown(contenido)

                st.session_state.messages.append(
                    {"role": "assistant", "content": contenido}
                )

            except Exception as error:
                st.error(
                    "No hemos podido procesar tu mensaje. "
                    "Vuelve a enviarlo en unos segundos."
                )
                print(f"Error del agente: {error}")


# ============================================================
# NUEVA CONVERSACIÓN
# ============================================================

if st.session_state.messages:
    _, centro, _ = st.columns([1, 1, 1])

    with centro:
        if st.button("Empezar de nuevo", key="nueva"):
            nueva_conversacion()
            st.rerun()


# ============================================================
# PIE
# ============================================================

st.markdown(
    '<div class="footer">Studio Alba, tu momento en Madrid</div>',
    unsafe_allow_html=True,
)
