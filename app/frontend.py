from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# CONFIGURACIÓN
# ============================================================

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
NOTEBOOK_PATH = APP_DIR / "prueba.ipynb"
DATA_DIR = PROJECT_DIR / "datos_negocio"
BUSINESS_FILE = PROJECT_DIR / "documentos_negocio" / "negocio.txt"

st.set_page_config(
    page_title="Studio Alba · AI Assistant",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# ESTILOS — inspirado en la referencia: dark UI + purple accent
# ============================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --bg: #08090b;
        --panel: #111216;
        --panel-2: #17181d;
        --panel-3: #1d1e24;
        --border: #292a31;
        --text: #f5f5f7;
        --muted: #92949f;
        --purple: #8b5cf6;
        --purple-2: #a78bfa;
        --green: #49d18d;
        --red: #ff6b7a;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: var(--bg);
        color: var(--text);
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    [data-testid="stSidebar"] {
        background: #0d0e11;
        border-right: 1px solid var(--border);
    }

    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1rem;
    }

    .block-container {
        padding: 1.2rem 1.5rem 1.5rem;
        max-width: 1500px;
    }

    .brand {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 6px 8px 18px;
    }

    .brand-icon {
        width: 34px;
        height: 34px;
        display: grid;
        place-items: center;
        border-radius: 10px;
        background: linear-gradient(145deg, #a855f7, #6d28d9);
        color: white;
        font-weight: 700;
        box-shadow: 0 8px 28px rgba(139, 92, 246, .25);
    }

    .brand-title { font-weight: 700; font-size: 15px; }
    .brand-subtitle { color: var(--muted); font-size: 11px; margin-top: 2px; }

    .section-label {
        color: #70727d;
        text-transform: uppercase;
        letter-spacing: .09em;
        font-size: 10px;
        font-weight: 700;
        margin: 18px 8px 8px;
    }

    .sidebar-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 9px 10px;
        border-radius: 10px;
        color: #b9bac2;
        font-size: 13px;
        margin-bottom: 2px;
    }

    .sidebar-item.active {
        background: #1d1828;
        color: white;
    }

    .sidebar-item .left { display: flex; gap: 9px; align-items: center; }

    .badge {
        min-width: 20px;
        padding: 2px 6px;
        text-align: center;
        border-radius: 20px;
        background: #25262d;
        color: #aaaab4;
        font-size: 10px;
    }

    .topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 2px 2px 16px;
        border-bottom: 1px solid var(--border);
        margin-bottom: 16px;
    }

    .eyebrow { color: var(--muted); font-size: 12px; }
    .page-title { font-size: 24px; font-weight: 600; margin-top: 3px; }

    .status {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        border: 1px solid var(--border);
        background: #121318;
        border-radius: 999px;
        padding: 7px 11px;
        color: #c9cad1;
        font-size: 11px;
    }

    .status-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--green);
        box-shadow: 0 0 10px rgba(73, 209, 141, .65);
    }

    .hero {
        background: radial-gradient(circle at 85% 20%, rgba(139,92,246,.14), transparent 28%), #111216;
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 22px;
        margin-bottom: 14px;
    }

    .hero h1 { font-size: 27px; margin: 0 0 8px; letter-spacing: -.03em; }
    .hero p { color: #a4a5ae; margin: 0; font-size: 13px; line-height: 1.6; }

    .suggestion {
        background: #17181d;
        border: 1px solid #292a31;
        border-radius: 12px;
        padding: 12px 14px;
        color: #cfd0d7;
        font-size: 12px;
        min-height: 64px;
    }

    .suggestion-title { color: white; font-weight: 600; margin-bottom: 5px; }

    .card {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 12px;
    }

    .card-title {
        font-size: 12px;
        font-weight: 600;
        color: #e9e9ed;
        margin-bottom: 12px;
    }

    .metric-value { font-size: 22px; font-weight: 700; }
    .metric-label { color: var(--muted); font-size: 11px; margin-top: 3px; }

    .conversation {
        min-height: 390px;
        max-height: 55vh;
        overflow-y: auto;
        padding-right: 4px;
    }

    .chat-row { display: flex; margin: 10px 0; }
    .chat-row.user { justify-content: flex-end; }

    .chat-bubble {
        max-width: 82%;
        padding: 12px 14px;
        border-radius: 14px;
        font-size: 13px;
        line-height: 1.55;
        white-space: pre-wrap;
    }

    .chat-bubble.assistant {
        background: #17181d;
        border: 1px solid var(--border);
        color: #dedee3;
        border-top-left-radius: 5px;
    }

    .chat-bubble.user {
        background: linear-gradient(145deg, #7c3aed, #6d28d9);
        color: white;
        border-top-right-radius: 5px;
    }

    .chat-avatar {
        width: 27px;
        height: 27px;
        border-radius: 9px;
        display: grid;
        place-items: center;
        margin-right: 8px;
        background: #26212f;
        color: #c4b5fd;
        font-size: 12px;
    }

    .info-row {
        display: flex;
        justify-content: space-between;
        gap: 15px;
        padding: 9px 0;
        border-bottom: 1px solid #24252b;
        font-size: 12px;
    }

    .info-row:last-child { border-bottom: none; }
    .info-key { color: var(--muted); }
    .info-value { color: #e6e6ea; text-align: right; }

    div[data-testid="stForm"] {
        background: #111216;
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 10px;
    }

    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
        background: #17181d !important;
        color: #f4f4f6 !important;
        border-color: #292a31 !important;
        border-radius: 10px !important;
    }

    .stButton > button, .stFormSubmitButton > button {
        border-radius: 10px;
        border: 1px solid #33234f;
        background: #24183a;
        color: #d8c9ff;
        font-weight: 600;
    }

    .stButton > button:hover, .stFormSubmitButton > button:hover {
        border-color: #8b5cf6;
        color: white;
    }

    .stTabs [data-baseweb="tab-list"] { gap: 4px; background: transparent; }
    .stTabs [data-baseweb="tab"] {
        background: #121318;
        border: 1px solid var(--border);
        border-radius: 9px;
        color: #aaaab4;
        padding: 7px 13px;
    }
    .stTabs [aria-selected="true"] { color: white; border-color: #51327e; background: #211933; }

    [data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

    .small-note { color: #6f717c; font-size: 10px; line-height: 1.5; }

    @media (max-width: 1100px) {
        .block-container { padding: 1rem; }
        .chat-bubble { max-width: 92%; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CARGAR EL AGENTE DIRECTAMENTE DESDE prueba.ipynb
# ============================================================

@st.cache_resource(show_spinner="Preparando el agente y la base de conocimiento...")
def load_agent_from_notebook():
    """Ejecuta las celdas de preparación de prueba.ipynb y devuelve `agent`.

    Se omiten únicamente las celdas finales de prueba (invoke/print), porque
    el frontend realizará las llamadas al agente.
    """
    if not NOTEBOOK_PATH.exists():
        raise FileNotFoundError(f"No se encuentra: {NOTEBOOK_PATH}")

    with NOTEBOOK_PATH.open("r", encoding="utf-8") as f:
        notebook = json.load(f)

    namespace = {
        "__name__": "__frontend_notebook__",
        "__file__": str(NOTEBOOK_PATH),
    }

    previous_cwd = Path.cwd()
    os.chdir(APP_DIR)
    try:
        for index, cell in enumerate(notebook.get("cells", [])):
            if cell.get("cell_type") != "code":
                continue

            source = "".join(cell.get("source", []))
            if not source.strip():
                continue

            # Las dos últimas celdas hacen una petición de prueba. No deben
            # ejecutarse cada vez que Streamlit recarga la interfaz.
            if index in {21, 22}:
                continue

            exec(compile(source, f"prueba.ipynb [cell {index}]", "exec"), namespace)
    finally:
        os.chdir(previous_cwd)

    if "agent" not in namespace:
        raise RuntimeError("El notebook se ha ejecutado, pero no se encontró la variable `agent`.")

    return namespace["agent"]


# ============================================================
# DATOS DEL NEGOCIO — SOLO PARA EL PANEL DEL PROPIETARIO
# ============================================================

@st.cache_data(ttl=30)

def load_business_data():
    from reservas.clientes import cargar_clientes
    from reservas.disponibilidad import cargar_citas

    data = {"clientes": cargar_clientes(), "citas": cargar_citas()}
    for name in ["ventas", "gastos", "empleados", "compras", "servicios"]:
        path = DATA_DIR / f"{name}.csv"
        if path.exists():
            df = pd.read_csv(path)
            df.columns = [str(c).replace("\ufeff", "") for c in df.columns]
            data[name] = df
    return data


@st.cache_data

def load_business_info():
    if BUSINESS_FILE.exists():
        return BUSINESS_FILE.read_text(encoding="utf-8")
    return "Información del negocio no disponible."


# ============================================================
# ESTADO DE LA SESIÓN
# ============================================================

if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"frontend_{uuid.uuid4().hex[:10]}"

if "messages" not in st.session_state:
    st.session_state.messages = []

if "section" not in st.session_state:
    st.session_state.section = "Asistente"


def reset_conversation():
    st.session_state.messages = []
    st.session_state.thread_id = f"frontend_{uuid.uuid4().hex[:10]}"


def ask_agent(message: str) -> str:
    agent = load_agent_from_notebook()

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": message,
                }
            ]
        },
        config={
            "configurable": {
                "thread_id": st.session_state.thread_id,
            }
        },
    )

    return result["messages"][-1].content


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown(
        """
        <div class="brand">
            <div class="brand-icon">✦</div>
            <div>
                <div class="brand-title">Studio Alba</div>
                <div class="brand-subtitle">AI Business Assistant</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("＋  Nueva conversación", use_container_width=True):
        reset_conversation()
        st.rerun()

    st.markdown('<div class="section-label">Workspace</div>', unsafe_allow_html=True)

    sections = [
        ("✦", "Asistente"),
        ("◷", "Citas"),
        ("♙", "Clientes"),
        ("↗", "Ventas"),
        ("◫", "Gastos"),
    ]

    for icon, label in sections:
        active = st.session_state.section == label
        if st.button(f"{icon}  {label}", key=f"nav_{label}", use_container_width=True):
            st.session_state.section = label
            st.rerun()

    st.markdown('<div class="section-label">Sistema</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sidebar-item"><div class="left"><span>●</span><span>Agente conectado</span></div><span class="badge">ON</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="small-note" style="padding:12px 8px;">El agente utiliza la información general de <b>negocio.txt</b>. Los CSV se muestran en el panel privado del propietario.</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# CONTENIDO PRINCIPAL
# ============================================================

business_data = load_business_data()

st.markdown(
    f"""
    <div class="topbar">
        <div>
            <div class="eyebrow">Workspace / {st.session_state.section}</div>
            <div class="page-title">{st.session_state.section}</div>
        </div>
        <div class="status"><span class="status-dot"></span> Agent online</div>
    </div>
    """,
    unsafe_allow_html=True,
)


if st.session_state.section == "Asistente":
    left, right = st.columns([2.15, 1], gap="large")

    with left:
        st.markdown(
            """
            <div class="hero">
                <h1>Hola, ¿en qué puedo ayudarte?</h1>
                <p>Gestiona Studio Alba, consulta información del negocio y obtén ayuda para tomar decisiones de forma rápida.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        s1, s2, s3 = st.columns(3)
        suggestions = [
            ("Información", "¿Cómo se llama el negocio?"),
            ("Servicios", "¿Qué servicios ofrece Studio Alba?"),
            ("Horario", "¿Cuál es el horario del negocio?"),
        ]
        for col, (title, text) in zip([s1, s2, s3], suggestions):
            with col:
                st.markdown(
                    f'<div class="suggestion"><div class="suggestion-title">{title}</div>{text}</div>',
                    unsafe_allow_html=True,
                )

        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

        st.markdown('<div class="card-title">Conversación</div>', unsafe_allow_html=True)

        with st.container(border=False):
            if not st.session_state.messages:
                st.markdown(
                    '<div class="chat-row"><div class="chat-avatar">✦</div><div class="chat-bubble assistant">Soy el asistente de Studio Alba. Puedo responder preguntas sobre la información general del negocio que tengo disponible.</div></div>',
                    unsafe_allow_html=True,
                )

            for message in st.session_state.messages:
                role = message["role"]
                css_role = "user" if role == "user" else "assistant"
                avatar = "Tú" if role == "user" else "✦"
                st.markdown(
                    f'<div class="chat-row {css_role}"><div class="chat-bubble {css_role}">{message["content"]}</div></div>',
                    unsafe_allow_html=True,
                )

        with st.form("chat_form", clear_on_submit=True):
            prompt = st.text_input(
                "",
                placeholder="Escribe una pregunta sobre Studio Alba...",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Enviar  ↗", use_container_width=True)

        if submitted and prompt.strip():
            user_message = prompt.strip()
            st.session_state.messages.append({"role": "user", "content": user_message})
            try:
                with st.spinner("Pensando..."):
                    response = ask_agent(user_message)
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as exc:
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": f"No he podido consultar el agente. Revisa el entorno y tu OPENAI_API_KEY.\n\nDetalle: {exc}",
                    }
                )
            st.rerun()

    with right:
        st.markdown('<div class="card"><div class="card-title">Studio Alba</div>', unsafe_allow_html=True)
        info = load_business_info().splitlines()
        parsed = {}
        for line in info:
            if ":" in line:
                key, value = line.split(":", 1)
                parsed[key.strip()] = value.strip()

        for key, value in parsed.items():
            st.markdown(
                f'<div class="info-row"><span class="info-key">{key.replace("_", " ").title()}</span><span class="info-value">{value}</span></div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="card"><div class="card-title">Resumen privado</div>', unsafe_allow_html=True)
        metrics = [
            ("Clientes", len(business_data.get("clientes", []))),
            ("Citas", len(business_data.get("citas", []))),
            ("Ventas", f'{business_data.get("ventas", pd.DataFrame()).get("importe", pd.Series(dtype=float)).sum():.0f} €'),
        ]
        for label, value in metrics:
            st.markdown(
                f'<div style="margin-bottom:14px"><div class="metric-value">{value}</div><div class="metric-label">{label}</div></div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown(
            '<div class="card"><div class="card-title">Privacidad</div><div class="small-note">Los datos de clientes, ventas y gastos se mantienen en este panel. No se envían al retriever del agente creado en <b>prueba.ipynb</b>.</div></div>',
            unsafe_allow_html=True,
        )


elif st.session_state.section in {"Citas", "Clientes", "Ventas", "Gastos"}:
    key_map = {
        "Citas": "citas",
        "Clientes": "clientes",
        "Ventas": "ventas",
        "Gastos": "gastos",
    }
    key = key_map[st.session_state.section]
    df = business_data.get(key, pd.DataFrame())

    st.markdown(
        f'<div class="card"><div class="card-title">Datos privados · {st.session_state.section}</div>',
        unsafe_allow_html=True,
    )
    if df.empty:
        st.info("No hay datos disponibles.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        '<div class="small-note">Esta sección es para el propietario del negocio. Estos datos no forman parte de la herramienta RAG del agente del notebook.</div>',
        unsafe_allow_html=True,
    )
