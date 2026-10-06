"""
Panel de la propietaria de Studio Alba: estadísticas del negocio y marketing.

Arranque:
    poetry run streamlit run app/panel_propietaria.py --server.port 8503

Acceso: define OWNER_PIN en el .env (distinto de PANEL_PIN, el de las empleadas:
aquí se ven ingresos, costes y nóminas). Sin PIN el panel no se abre.
"""

import html
import os
from urllib.parse import quote

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

import analitica as an
from reservas import config
from reservas.clientes import normalizar_telefono

load_dotenv()

st.set_page_config(
    page_title="Studio Alba · Panel de la propietaria",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Paleta: verde bosque para lo principal, latón solo como detalle.
VERDE, VERDE_OSCURO, VERDE_SUAVE = "#1f4d3a", "#10231b", "#e3ece6"
LATON, ROJO, GRIS = "#b08d57", "#b5523f", "#8a938d"

# ============================================================
# ESTILO
# ============================================================

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Bodoni+Moda:opsz,wght@6..96,400;6..96,500&family=Manrope:wght@400;500;600;700&display=swap');

    :root {
        --verde: #1f4d3a; --verde-oscuro: #10231b; --verde-suave: #e3ece6;
        --laton: #b08d57; --rojo: #b5523f; --gris: #8a938d; --tinta: #16211b;
        --fondo: #eef1ee; --tarjeta: #ffffff;
        --display: 'Bodoni Moda', 'Didot', Georgia, serif;
        --texto: 'Manrope', 'Helvetica Neue', Arial, sans-serif;
    }

    .stApp { background: var(--fondo); font-family: var(--texto); color: var(--tinta); }
    .stApp p, .stApp label, .stApp li { font-family: var(--texto); }
    .block-container { max-width: 1240px; padding: 1.6rem 2rem 4rem; }

    [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer { display: none !important; }
    header[data-testid="stHeader"] { background: transparent; }

    /* ---------- Barra lateral ---------- */
    [data-testid="stSidebar"] { background: var(--verde-oscuro); border-right: none; }
    [data-testid="stSidebar"] * { color: #c5d3ca; }
    [data-testid="stSidebarCollapseButton"] { display: none; }
    [data-testid="stSidebar"] .block-container, [data-testid="stSidebarUserContent"] { padding-top: 1.6rem; }

    .marca { display: flex; align-items: baseline; gap: 0.6rem; }
    .marca-simbolo { color: var(--laton) !important; font-size: 1.2rem; }
    .marca-nombre { font-family: var(--display); font-size: 1.7rem; color: #f5f2ea !important; letter-spacing: 0.01em; }
    .marca-linea { width: 36px; height: 1px; background: var(--laton); margin: 0.9rem 0 0.7rem; }
    .marca-sub { font-size: 0.78rem; color: #8ea398 !important; margin-bottom: 1.6rem; }

    [data-testid="stSidebar"] [role="radiogroup"] { gap: 0.15rem; }
    [data-testid="stSidebar"] [role="radiogroup"] label { padding: 0.62rem 0.9rem; border-radius: 10px; width: 100%; cursor: pointer; }
    [data-testid="stSidebar"] [role="radiogroup"] label > div > div:first-child { display: none; }
    [data-testid="stSidebar"] [role="radiogroup"] label p { font-size: 0.95rem; font-weight: 500; color: #a9bbb0 !important; }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover { background: rgba(255,255,255,0.04); }
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) { background: rgba(255,255,255,0.09); box-shadow: inset 3px 0 0 var(--laton); }
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p { color: #ffffff !important; font-weight: 600; }
    [data-testid="stSidebar"] button { background: transparent; border: 1px solid rgba(255,255,255,0.18); color: #c5d3ca; border-radius: 10px; }
    [data-testid="stSidebar"] button:hover { border-color: var(--laton); color: #fff; }

    /* ---------- Título de página y selector de periodo ---------- */
    .pagina-titulo { font-family: var(--display); font-size: 2.3rem; line-height: 1.1; color: var(--tinta); margin: 0 0 1.1rem; }
    .pagina-sub { color: var(--gris); font-size: 0.9rem; margin-bottom: 1.1rem; }

    .st-key-periodo [role="radiogroup"] { display: inline-flex; flex-wrap: nowrap; gap: 0.1rem; background: #e2e8e3; padding: 4px; border-radius: 12px; }
    .st-key-periodo [role="radiogroup"] label { padding: 0.36rem 0.85rem; border-radius: 9px; cursor: pointer; margin: 0; white-space: nowrap; }
    .st-key-periodo [role="radiogroup"] label > div > div:first-child { display: none; }
    .st-key-periodo [role="radiogroup"] label p { font-size: 0.85rem; font-weight: 600; color: #6b756f; white-space: nowrap; }
    .st-key-periodo [role="radiogroup"] label:has(input:checked) { background: var(--verde); }
    .st-key-periodo [role="radiogroup"] label:has(input:checked) p { color: #ffffff; }

    /* ---------- Tarjetas ---------- */
    [class*="st-key-tarjeta"] {
        background: var(--tarjeta); border: none !important; border-radius: 18px;
        box-shadow: 0 1px 2px rgba(16,35,27,0.04), 0 10px 28px rgba(16,35,27,0.05);
        padding: 1.5rem 1.6rem 1.3rem;
    }
    .tarjeta-titulo { font-family: var(--display); font-size: 1.45rem; line-height: 1.15; color: var(--tinta); }
    .tarjeta-sub { color: var(--gris); font-size: 0.85rem; margin: 0.25rem 0 1rem; }

    /* ---------- Indicadores ---------- */
    .kpi { background: var(--tarjeta); border-radius: 18px; padding: 1.2rem 1.4rem 1.25rem; min-height: 8.9rem;
           box-shadow: 0 1px 2px rgba(16,35,27,0.04), 0 10px 28px rgba(16,35,27,0.05); }
    .kpi-etiqueta { color: var(--gris); font-size: 0.85rem; font-weight: 500; }
    .kpi-valor { font-family: var(--display); font-size: 2.2rem; line-height: 1.15; margin: 0.35rem 0 0.55rem; color: var(--tinta); }
    .chip { display: inline-block; border-radius: 8px; padding: 0.15rem 0.55rem; font-size: 0.78rem; font-weight: 700; }
    .chip.sube { background: #e1efe6; color: #1f6b4a; }
    .chip.baja { background: #f7e6e2; color: #a5432f; }
    .chip.neutro { background: #eef1ee; color: #6b756f; }
    .kpi-nota { color: var(--gris); font-size: 0.78rem; margin-left: 0.4rem; }

    /* ---------- Listas con barras ---------- */
    .fila { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(70px, 1fr) auto; align-items: center; gap: 1rem; padding: 0.5rem 0; font-size: 0.9rem; }
    .fila-etiqueta { color: var(--tinta); font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 1.25; }
    .pista { background: var(--verde-suave); border-radius: 99px; height: 8px; overflow: hidden; }
    .relleno { background: var(--verde); height: 100%; border-radius: 99px; }
    .relleno.laton { background: var(--laton); }
    .relleno.rojo { background: var(--rojo); }
    .fila-valor { font-weight: 700; text-align: right; min-width: 4.5rem; }
    .fila-extra { display: block; color: var(--gris); font-weight: 500; font-size: 0.76rem; margin-top: 0.05rem; }

    /* ---------- Celdas teñidas ---------- */
    .celdas { display: grid; gap: 0.7rem; }
    .celda-etiqueta { color: var(--gris); font-size: 0.8rem; margin-bottom: 0.4rem; }
    .celda { border-radius: 10px; padding: 0.7rem 0.9rem; font-weight: 700; font-size: 1.05rem; }
    .celda small { font-weight: 500; color: #56645b; margin-left: 0.3rem; }

    /* ---------- Actividad (cifras en fila) ---------- */
    .cifras { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem 1.2rem; }
    .cifra-etiqueta { color: var(--gris); font-size: 0.8rem; }
    .cifra-valor { font-size: 1.25rem; font-weight: 700; margin-top: 0.15rem; }

    .idea { display: flex; gap: 0.7rem; padding: 0.55rem 0; line-height: 1.5; font-size: 0.93rem; border-bottom: 1px solid #eef1ee; }
    .idea:last-child { border-bottom: none; }
    .idea::before { content: "✦"; color: var(--laton); }

    /* ---------- Controles ---------- */
    div.stButton > button, div.stDownloadButton > button {
        background: var(--verde); color: #ffffff; border: none; border-radius: 10px; padding: 0.55rem 1.3rem; font-weight: 600;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover { background: #29634b; color: #ffffff; }
    button:focus-visible, input:focus-visible, textarea:focus-visible { outline: 2px solid var(--laton) !important; outline-offset: 2px; }
    [data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; }

    #vg-tooltip-element { font-family: var(--texto) !important; border-radius: 12px !important; border: none !important;
        box-shadow: 0 8px 24px rgba(16,35,27,0.14) !important; padding: 0.7rem 0.9rem !important; }

    @media (max-width: 800px) { .block-container { padding: 1rem; } .fila { grid-template-columns: 1fr 1fr auto; } }
    @media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# ACCESO
# ============================================================

PIN = os.getenv("OWNER_PIN", "").strip()

if not PIN:
    st.error("El panel está desactivado. Añade OWNER_PIN al archivo .env y vuelve a arrancarlo.")
    st.stop()

if not st.session_state.get("acceso"):
    _, centro, _ = st.columns([1, 1, 1])

    with centro:
        st.markdown(
            "<div class='pagina-titulo' style='margin-top:4rem'>Studio Alba</div>"
            "<div class='pagina-sub'>Panel de la propietaria</div>",
            unsafe_allow_html=True,
        )
        pin_introducido = st.text_input("PIN de acceso", type="password")

        if st.button("Entrar"):
            if pin_introducido == PIN:
                st.session_state.acceso = True
                st.rerun()
            else:
                st.error("PIN incorrecto.")

    st.stop()


# ============================================================
# AYUDAS DE FORMATO Y COMPONENTES
# ============================================================

def esc(texto):
    return html.escape(str(texto))


def num(x, decimales=0):
    """Formato español: 1.234,5"""
    return f"{x:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def eur(x, decimales=0):
    return f"{num(x, decimales)} €"


def pct(x):
    return f"{x * 100:.0f} %"


def variacion(actual, anterior):
    if not anterior:
        return None
    return f"{(actual - anterior) / abs(anterior) * 100:+.0f} %"


_contador_tarjetas = 0
_alturas = {}


def tarjeta(titulo, subtitulo="", alto=None):
    """
    Tarjeta blanca redondeada con título y subtítulo. Se usa con `with`.
    alto: altura mínima en píxeles, para que las tarjetas de una misma fila queden iguales.
    """
    global _contador_tarjetas
    _contador_tarjetas += 1

    if alto:
        _alturas[f"tarjeta_{_contador_tarjetas}"] = alto

    contenedor = st.container(border=True, key=f"tarjeta_{_contador_tarjetas}")
    with contenedor:
        st.markdown(
            f"<div class='tarjeta-titulo'>{esc(titulo)}</div><div class='tarjeta-sub'>{esc(subtitulo)}</div>",
            unsafe_allow_html=True,
        )
    return contenedor


def kpi(columna, etiqueta, valor, cambio=None, inverso=False, nota=""):
    """Indicador con la variación en una etiqueta de color. inverso=True: que suba es malo (costes)."""
    if cambio is None:
        chip = f"<span class='chip neutro'>{esc(nota)}</span>" if nota else ""
    else:
        sube = cambio.startswith("+")
        bueno = sube != inverso if cambio not in ("+0 %", "-0 %") else None
        clase = "neutro" if bueno is None else ("sube" if bueno else "baja")
        flecha = "▲" if sube else "▼"
        chip = f"<span class='chip {clase}'>{flecha} {esc(cambio.lstrip('+-'))}</span><span class='kpi-nota'>vs. periodo anterior</span>"

    columna.markdown(
        f"<div class='kpi'><div class='kpi-etiqueta'>{esc(etiqueta)}</div>"
        f"<div class='kpi-valor'>{esc(valor)}</div>{chip}</div>",
        unsafe_allow_html=True,
    )


def lista_barras(filas, color=""):
    """filas: [(etiqueta, valor_texto, fraccion 0-1, extra_texto)]"""
    if not filas:
        st.caption("Sin datos en este periodo.")
        return

    st.markdown(
        "".join(
            f"<div class='fila'><div class='fila-etiqueta' title='{esc(e)}'>{esc(e)}"
            + (f"<span class='fila-extra'>{esc(x)}</span>" if x else "") + "</div>"
            f"<div class='pista'><div class='relleno {color}' style='width:{max(min(f, 1), 0.02) * 100:.0f}%'></div></div>"
            f"<div class='fila-valor'>{esc(v)}</div></div>"
            for e, v, f, x in filas
        ),
        unsafe_allow_html=True,
    )


def celdas_teñidas(items):
    """items: [(etiqueta, texto, detalle, fraccion 0-1)]: una fila de celdas con el fondo más o menos intenso."""
    columnas = "".join(
        f"<div><div class='celda-etiqueta'>{esc(e)}</div>"
        f"<div class='celda' style='background:rgba(31,77,58,{0.06 + 0.24 * f:.2f})'>{esc(t)}<small>{esc(d)}</small></div></div>"
        for e, t, d, f in items
    )
    st.markdown(f"<div class='celdas' style='grid-template-columns:repeat({len(items)},1fr)'>{columnas}</div>", unsafe_allow_html=True)


def cifras(items):
    """items: [(etiqueta, valor_texto)] en cuadrícula de dos columnas."""
    st.markdown(
        "<div class='cifras'>" + "".join(
            f"<div><div class='cifra-etiqueta'>{esc(e)}</div><div class='cifra-valor'>{esc(v)}</div></div>" for e, v in items
        ) + "</div>",
        unsafe_allow_html=True,
    )


def fraccion(valor, maximo):
    return valor / maximo if maximo else 0.0


def dibujar(chart, alto=300):
    chart = (
        chart.properties(height=alto, background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axis(labelFont="Manrope", titleFont="Manrope", labelColor=GRIS, titleColor=GRIS, labelFontSize=12, domain=False, ticks=False)
        .configure_legend(labelFont="Manrope", labelColor="#56645b", symbolType="circle", orient="top", title=None)
    )
    st.altair_chart(chart, theme=None, width="stretch")


EJE_Y = alt.Axis(grid=True, gridDash=[3, 4], gridColor="#e3e8e4", format="~s", title=None, tickCount=5)
EJE_MES = alt.Axis(grid=False, title=None, labelPadding=8, format="%b %Y", labelAngle=0)
EJE_X = alt.Axis(grid=False, title=None, labelPadding=8, format="%b %Y", labelAngle=0, tickCount={"interval": "month", "step": 1})


# ============================================================
# DATOS Y PERIODO
# ============================================================

hoy = pd.Timestamp(config.ahora().date())
datos = an.cargar_datos()

primer_dia_mes = hoy.replace(day=1)
opciones_periodo = {
    "Este mes": (primer_dia_mes, hoy),
    "Mes anterior": (primer_dia_mes - pd.DateOffset(months=1), primer_dia_mes - pd.Timedelta(days=1)),
    "Últimos 3 meses": (primer_dia_mes - pd.DateOffset(months=2), hoy),
    "Últimos 6 meses": (primer_dia_mes - pd.DateOffset(months=5), hoy),
}
fechas = [f for f in (datos["ventas"]["fecha"].min(), datos["clientes"]["fecha_alta"].min()) if pd.notna(f)]
opciones_periodo["Todo el historial"] = (min(fechas) if fechas else primer_dia_mes, hoy)

SECCIONES = ["Resumen", "Ingresos", "Costes", "Clientes", "Agenda", "Marketing"]

with st.sidebar:
    st.markdown(
        "<div class='marca'><span class='marca-simbolo'>✦</span><span class='marca-nombre'>Studio Alba</span></div>"
        "<div class='marca-linea'></div><div class='marca-sub'>Panel de la propietaria</div>",
        unsafe_allow_html=True,
    )
    seccion = st.radio("Sección", SECCIONES, key="seccion", label_visibility="collapsed")

    st.write("")
    if st.button("Cerrar sesión", key="salir"):
        st.session_state.acceso = False
        st.rerun()

encabezados = {
    "Resumen": "Cómo va el negocio", "Ingresos": "Ingresos", "Costes": "Costes",
    "Clientes": "Clientes", "Agenda": "Agenda", "Marketing": "Marketing",
}
st.markdown(f"<div class='pagina-titulo'>{encabezados[seccion]}</div>", unsafe_allow_html=True)

col_periodo, col_fechas = st.columns([7, 4])
with col_periodo:
    etiqueta_periodo = st.radio("Periodo", list(opciones_periodo), index=2, horizontal=True, key="periodo", label_visibility="collapsed")

desde, hasta = (pd.Timestamp(f) for f in opciones_periodo[etiqueta_periodo])
desde_ant, hasta_ant = an.periodo_anterior(desde, hasta)
comparar = etiqueta_periodo != "Todo el historial" and not an.filtrar(datos["ventas"], desde_ant, hasta_ant).empty

with col_fechas:
    st.markdown(
        f"<div class='pagina-sub' style='text-align:right;padding-top:0.55rem'>{desde:%d/%m/%Y} – {hasta:%d/%m/%Y}</div>",
        unsafe_allow_html=True,
    )

k = an.kpis(datos, desde, hasta)
k_ant = an.kpis(datos, desde_ant, hasta_ant) if comparar else None


def cambio(clave):
    return variacion(k[clave], k_ant[clave]) if comparar else None


resumen_clientes = an.resumen_clientes(datos, hoy)
ocupacion = an.ocupacion(datos, desde, hasta, hoy)
origen = an.origen_reservas(datos, desde, hasta)
por_servicio = an.ingresos_por_servicio(datos, desde, hasta)
por_profesional = an.ingresos_por_profesional(datos, desde, hasta)


def filas_ingresos(df, columna_etiqueta):
    maximo = df["ingresos"].max() if not df.empty else 0
    return [(r[columna_etiqueta], eur(r["ingresos"]), fraccion(r["ingresos"], maximo), f"{int(r['servicios'])} serv.") for _, r in df.iterrows()]


def filas_ocupacion():
    return [(r["empleado"], pct(r["ocupacion"]), r["ocupacion"], "") for _, r in ocupacion.iterrows()]


def filas_origen():
    total = origen["citas"].sum() if not origen.empty else 0
    return [(r["origen"], pct(fraccion(r["citas"], total)), fraccion(r["citas"], total), f"{int(r['citas'])} citas") for _, r in origen.iterrows()]


# ============================================================
# RESUMEN
# ============================================================

if seccion == "Resumen":
    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "Ingresos", eur(k["ingresos"]), cambio("ingresos"))
    kpi(c2, "Costes", eur(k["costes"]), cambio("costes"), inverso=True)
    kpi(c3, "Beneficio", eur(k["beneficio"]), cambio("beneficio"))
    kpi(c4, "Margen", pct(k["margen"]),
        f"{(k['margen'] - k_ant['margen']) * 100:+.0f} pts" if comparar else None)

    st.write("")
    izquierda, derecha = st.columns([2, 1])

    with izquierda:
        with tarjeta("Ingresos y costes", "Evolución mensual", alto=505):
            serie = an.serie_mensual(datos, desde, hasta)
            largo = serie.melt(id_vars="mes", value_vars=["ingresos", "costes"], var_name="concepto", value_name="euros")
            largo["concepto"] = largo["concepto"].map({"ingresos": "Ingresos", "costes": "Costes"})

            cursor = alt.selection_point(nearest=True, on="pointerover", fields=["mes"], empty=False)
            base = alt.Chart(largo).encode(x=alt.X("mes:T", axis=EJE_X), y=alt.Y("euros:Q", axis=EJE_Y))

            ingresos_area = (
                alt.Chart(largo[largo["concepto"] == "Ingresos"])
                .mark_area(
                    interpolate="monotone", line={"color": VERDE, "strokeWidth": 3},
                    color=alt.Gradient(gradient="linear", x1=1, x2=1, y1=1, y2=0,
                                       stops=[alt.GradientStop(color="rgba(47,125,91,0.0)", offset=0),
                                              alt.GradientStop(color="rgba(47,125,91,0.24)", offset=1)]),
                ).encode(x=alt.X("mes:T", axis=EJE_X), y=alt.Y("euros:Q", axis=EJE_Y))
            )
            costes_linea = (
                alt.Chart(largo[largo["concepto"] == "Costes"])
                .mark_line(interpolate="monotone", color=LATON, strokeWidth=2.5, strokeDash=[6, 4])
                .encode(x=alt.X("mes:T", axis=EJE_X), y=alt.Y("euros:Q", axis=EJE_Y))
            )
            puntos = (
                base.mark_point(size=90, filled=True, opacity=0)
                .encode(color=alt.Color("concepto:N", scale=alt.Scale(domain=["Ingresos", "Costes"], range=[VERDE, LATON]),
                                        legend=alt.Legend(title=None, orient="top", direction="horizontal", offset=12)),
                        opacity=alt.condition(cursor, alt.value(1), alt.value(0)))
                .add_params(cursor)
            )
            regla = (
                alt.Chart(largo).mark_rule(color="#c9d3cc", strokeDash=[4, 4])
                .encode(x="mes:T", opacity=alt.condition(cursor, alt.value(1), alt.value(0)),
                        tooltip=[alt.Tooltip("mes:T", title="Mes", format="%B %Y"),
                                 alt.Tooltip("concepto:N", title="Concepto"),
                                 alt.Tooltip("euros:Q", title="Euros", format=",.0f")])
                .add_params(cursor)
            )
            dibujar(alt.layer(ingresos_area, costes_linea, regla, puntos), alto=385)

    with derecha:
        with tarjeta("Lo que más factura", "Ingresos por servicio", alto=505):
            lista_barras(filas_ingresos(por_servicio.head(8), "servicio"))

    st.write("")
    a, b, c = st.columns(3)

    with a:
        with tarjeta("Actividad", "Lo que ha pasado en el periodo", alto=255):
            cifras([
                ("Servicios realizados", num(k["servicios"])),
                ("Ticket medio", eur(k["ticket_medio"], 1)),
                ("Clientes atendidos", num(k["clientes_atendidos"])),
                ("Ocupación de la agenda", pct(float(ocupacion["ocupacion"].mean()) if not ocupacion.empty else 0.0)),
            ])

    with b:
        with tarjeta("Clientes", "Cómo están ahora mismo", alto=255):
            total = max(len(resumen_clientes[resumen_clientes["visitas"] > 0]), 1)
            conteo = resumen_clientes["segmento"].value_counts()
            lista_barras([
                ("Activos", num(int(conteo.get("Recurrente", 0) + conteo.get("Nueva", 0))), fraccion(conteo.get("Recurrente", 0) + conteo.get("Nueva", 0), total), ""),
                ("En riesgo", num(int(conteo.get("En riesgo", 0))), fraccion(conteo.get("En riesgo", 0), total), ""),
                ("Perdidos", num(int(conteo.get("Perdida", 0))), fraccion(conteo.get("Perdida", 0), total), ""),
            ])

    with c:
        with tarjeta("Cómo reservan", "Canal de cada cita", alto=255):
            lista_barras(filas_origen(), color="laton")

    st.write("")
    with tarjeta("Qué dicen los números", "Pistas automáticas: comprueba siempre el dato en su sección"):
        for frase in an.ideas(datos, desde, hasta, hoy):
            st.markdown(f"<div class='idea'><div>{esc(frase)}</div></div>", unsafe_allow_html=True)

    st.caption("Costes = gastos + compras a proveedores + nóminas (repartidas por días de cada mes).")


# ============================================================
# INGRESOS
# ============================================================

elif seccion == "Ingresos":
    if por_servicio.empty:
        st.info("No hay ventas en este periodo.")
    else:
        izquierda, derecha = st.columns([3, 2])

        with izquierda:
            with tarjeta("Por servicio", "Lo facturado y cuántas veces se ha hecho"):
                lista_barras(filas_ingresos(por_servicio, "servicio"))
                st.write("")
                st.dataframe(
                    por_servicio, hide_index=True, width="stretch",
                    column_config={
                        "servicio": "Servicio",
                        "ingresos": st.column_config.NumberColumn("Ingresos", format="%.0f €"),
                        "servicios": "Veces realizado",
                        "ticket_medio": st.column_config.NumberColumn("Precio medio", format="%.1f €"),
                    },
                )

        with derecha:
            with tarjeta("Por profesional", "Ingresos de cada una"):
                lista_barras(filas_ingresos(por_profesional, "empleado"), color="laton")
                st.write("")
                st.dataframe(
                    por_profesional, hide_index=True, width="stretch",
                    column_config={
                        "empleado": "Profesional",
                        "ingresos": st.column_config.NumberColumn("Ingresos", format="%.0f €"),
                        "servicios": "Servicios",
                        "ticket_medio": st.column_config.NumberColumn("Ticket medio", format="%.1f €"),
                    },
                )


# ============================================================
# COSTES
# ============================================================

elif seccion == "Costes":
    c1, c2, c3 = st.columns(3)
    kpi(c1, "Gastos fijos y suministros", eur(k["gastos"]), cambio("gastos"), inverso=True, nota="en el periodo")
    kpi(c2, "Compras a proveedores", eur(k["compras"]), cambio("compras"), inverso=True, nota="en el periodo")
    kpi(c3, "Nóminas", eur(k["nominas"]), nota="repartidas por días")

    st.write("")
    izquierda, derecha = st.columns([2, 3])

    with izquierda:
        with tarjeta("En qué se va el dinero", "Costes por categoría", alto=400):
            por_categoria = an.costes_por_categoria(datos, desde, hasta)
            maximo = por_categoria["importe"].max() if not por_categoria.empty else 0
            lista_barras([(r["categoria"], eur(r["importe"]), fraccion(r["importe"], maximo), "") for _, r in por_categoria.iterrows()], color="laton")

    with derecha:
        with tarjeta("Compras por proveedor", "Producto y unidades compradas en el periodo", alto=400):
            compras = an.filtrar(datos["compras"], desde, hasta)
            if compras.empty:
                st.caption("Sin compras en este periodo.")
            else:
                por_proveedor = compras.groupby(["proveedor", "producto"]).agg(unidades=("cantidad", "sum"), importe=("importe", "sum")).reset_index().sort_values("importe", ascending=False)
                st.dataframe(
                    por_proveedor, hide_index=True, width="stretch",
                    column_config={
                        "proveedor": "Proveedor", "producto": "Producto", "unidades": "Unidades",
                        "importe": st.column_config.NumberColumn("Importe", format="%.0f €"),
                    },
                )

    st.caption("Las compras a proveedores se suman aparte de los gastos: si alguna ya aparece en gastos.csv, se contaría dos veces.")


# ============================================================
# CLIENTES
# ============================================================

elif seccion == "Clientes":
    conteo = resumen_clientes["segmento"].value_counts()
    activos = int(conteo.get("Nueva", 0) + conteo.get("Recurrente", 0))
    nuevos = an.nuevos_por_mes(datos, desde, hasta)

    c1, c2, c3, c4 = st.columns(4)
    kpi(c1, "Clientes activos", num(activos), nota=f"últimos {an.DIAS_EN_RIESGO} días")
    kpi(c2, "Nuevos en el periodo", num(int(nuevos["clientes_nuevos"].sum())), nota="altas")
    kpi(c3, "Han vuelto", pct(an.tasa_repeticion(resumen_clientes)), nota="2 o más visitas")
    kpi(c4, "Por recuperar", num(int(conteo.get("En riesgo", 0) + conteo.get("Perdida", 0))), nota="sin venir")

    st.write("")
    with tarjeta("Cómo están los clientes", f"En riesgo: más de {an.DIAS_EN_RIESGO} días sin venir. Perdidos: más de {an.DIAS_PERDIDA}"):
        orden = ["Recurrente", "Nueva", "En riesgo", "Perdida", "Sin visitas"]
        total = max(int(resumen_clientes.shape[0]), 1)
        nombres = {"Recurrente": "Recurrentes", "Nueva": "Nuevos", "En riesgo": "En riesgo", "Perdida": "Perdidos", "Sin visitas": "Sin visitas"}
        celdas_teñidas([(nombres[s], num(int(conteo.get(s, 0))), pct(conteo.get(s, 0) / total), conteo.get(s, 0) / total) for s in orden])

    st.write("")
    izquierda, derecha = st.columns([2, 3])

    with izquierda:
        with tarjeta("Clientes nuevos", "Altas por mes", alto=520):
            dibujar(
                alt.Chart(nuevos).mark_bar(color=VERDE, cornerRadiusTopLeft=6, cornerRadiusTopRight=6, size=32).encode(
                    x=alt.X("mes:O", timeUnit="yearmonth", axis=EJE_MES),
                    y=alt.Y("clientes_nuevos:Q", axis=EJE_Y),
                    tooltip=[alt.Tooltip("mes:T", format="%B %Y", title="Mes"), alt.Tooltip("clientes_nuevos:Q", title="Altas")],
                ),
                alto=390,
            )

    with derecha:
        with tarjeta("Los que más gastan", "Los 10 clientes con más gasto acumulado", alto=520):
            mejores = resumen_clientes[resumen_clientes["visitas"] > 0].sort_values("gasto_total", ascending=False).head(10)
            st.dataframe(
                mejores[["nombre", "visitas", "gasto_total", "ultima_visita", "vip"]],
                hide_index=True, width="stretch",
                column_config={
                    "nombre": "Cliente", "visitas": "Visitas",
                    "gasto_total": st.column_config.NumberColumn("Gasto total", format="%.0f €"),
                    "ultima_visita": st.column_config.DateColumn("Última visita", format="DD/MM/YYYY"),
                    "vip": st.column_config.CheckboxColumn("VIP", help="3 o más visitas y entre el 20 % que más gasta"),
                },
            )


# ============================================================
# AGENDA
# ============================================================

elif seccion == "Agenda":
    proximos = datos["citas"][
        (datos["citas"]["estado"] == "confirmada")
        & (datos["citas"]["fecha"] > hoy)
        & (datos["citas"]["fecha"] <= hoy + pd.Timedelta(days=7))
    ]
    web = float(origen.loc[origen["origen"] == "Web (asistente)", "citas"].sum() / origen["citas"].sum()) if not origen.empty else 0.0

    c1, c2, c3 = st.columns(3)
    kpi(c1, "Citas en los próximos 7 días", num(len(proximos)), nota="confirmadas")
    kpi(c2, "Cancelaciones", pct(an.tasa_cancelacion(datos, desde, hasta)), nota="del periodo")
    kpi(c3, "Reservas por el asistente web", pct(web), nota="del periodo")

    st.write("")
    a, b = st.columns(2)

    with a:
        with tarjeta("Ocupación", "Horas reservadas frente a horas de apertura (hasta hoy)", alto=255):
            lista_barras(filas_ocupacion())

    with b:
        with tarjeta("Cómo reservan", "Canal de cada cita", alto=255):
            lista_barras(filas_origen(), color="laton")

    st.write("")
    with tarjeta("Cuándo se llena la agenda", "Citas por día de la semana y hora de inicio"):
        mapa = an.mapa_de_horas(datos, desde, hasta)
        if mapa.empty:
            st.info("Sin citas en este periodo.")
        else:
            dibujar(
                alt.Chart(mapa).mark_rect(cornerRadius=4, stroke="#ffffff", strokeWidth=2).encode(
                    x=alt.X("dia:N", sort=an.DIAS_SEMANA, axis=alt.Axis(title=None, labelAngle=0, labelExpr="upper(slice(datum.value, 0, 1)) + slice(datum.value, 1)")),
                    y=alt.Y("hora:O", axis=alt.Axis(title=None, labelExpr="datum.value + ':00'")),
                    color=alt.Color("citas:Q", title="Citas", scale=alt.Scale(range=["#eef3ef", VERDE]), legend=alt.Legend(orient="right")),
                    tooltip=["dia", "hora", "citas"],
                ),
                alto=380,
            )
    st.caption("La ocupación no descuenta los huecos que las profesionales bloquean.")


# ============================================================
# MARKETING
# ============================================================

else:
    marketing = an.marketing_mensual(datos, desde, hasta)
    gasto_mk = float(marketing["gasto_marketing"].sum())
    nuevos_mk = int(marketing["clientes_nuevos"].sum())

    c1, c2, c3 = st.columns(3)
    kpi(c1, "Gasto en marketing", eur(gasto_mk), nota="en el periodo")
    kpi(c2, "Clientes nuevos", num(nuevos_mk), nota="altas")
    kpi(c3, "Coste por cliente nuevo", eur(gasto_mk / nuevos_mk, 1) if nuevos_mk else "-", nota="aproximado")

    st.write("")
    with tarjeta("¿Se nota lo que invertimos?", "Barras: dinero en marketing. Línea: clientes nuevos. Que suban a la vez sugiere relación, pero no la demuestra"):
        base = alt.Chart(marketing).encode(x=alt.X("mes:O", timeUnit="yearmonth", axis=EJE_MES))
        barras = base.mark_bar(color="#c9d8ce", cornerRadiusTopLeft=6, cornerRadiusTopRight=6, size=34).encode(
            y=alt.Y("gasto_marketing:Q", axis=alt.Axis(title=None, grid=True, gridDash=[3, 4], gridColor="#e3e8e4", format="~s")),
            tooltip=[alt.Tooltip("mes:T", format="%B %Y", title="Mes"), alt.Tooltip("gasto_marketing:Q", title="Marketing (€)", format=",.0f"), alt.Tooltip("clientes_nuevos:Q", title="Clientes nuevos")],
        )
        linea = base.mark_line(color=VERDE, strokeWidth=3, interpolate="monotone", point=alt.OverlayMarkDef(color=VERDE, size=70, filled=True)).encode(
            y=alt.Y("clientes_nuevos:Q", axis=alt.Axis(title=None, orient="right", grid=False)),
        )
        dibujar(alt.layer(barras, linea).resolve_scale(y="independent"), alto=300)

    st.write("")
    with tarjeta("Recuperar clientes que han dejado de venir", "Ordenados por lo que han gastado. Los enlaces abren WhatsApp con el mensaje escrito; no se envía nada hasta que pulses enviar"):
        minimo = st.slider("Días sin venir (mínimo)", 30, 180, an.DIAS_EN_RIESGO, step=15, key="dias_minimos")
        lista = an.lista_reactivacion(resumen_clientes, minimo)

        if lista.empty:
            st.success("No hay clientes en esa situación.")
        else:
            st.markdown(f"**{len(lista)} clientes** llevan más de {minimo} días sin venir y han gastado **{eur(lista['gasto_total'].sum())}** en total.")

            plantilla = st.text_area(
                "Mensaje (usa {nombre} para poner el nombre)",
                "Hola {nombre}, hace tiempo que no te vemos por Studio Alba. Esta semana tenemos huecos y "
                "nos encantaría verte. ¿Quieres que te reservemos una cita?",
                key="plantilla_mensaje",
            )

            def enlace_whatsapp(fila):
                texto = plantilla.replace("{nombre}", str(fila["nombre"]).split()[0])
                telefono = normalizar_telefono(fila["telefono"])
                if len(telefono) == 9 and telefono[0] in "67":
                    return f"https://wa.me/34{telefono}?text={quote(texto)}"
                return f"https://wa.me/?text={quote(texto)}"        # sin número válido: se elige el contacto en WhatsApp

            lista = lista.assign(whatsapp=lista.apply(enlace_whatsapp, axis=1))

            st.dataframe(
                lista.head(30), hide_index=True, width="stretch",
                column_config={
                    "nombre": "Cliente", "telefono": "Teléfono",
                    "dias_desde_ultima": "Días sin venir",
                    "ultima_visita": st.column_config.DateColumn("Última visita", format="DD/MM/YYYY"),
                    "ultimo_servicio": "Último servicio", "visitas": "Visitas",
                    "gasto_total": st.column_config.NumberColumn("Ha gastado", format="%.0f €"),
                    "whatsapp": st.column_config.LinkColumn("WhatsApp", display_text="Abrir chat"),
                },
            )
            st.caption("Se muestran los 30 primeros; la descarga incluye todos.")

            st.download_button(
                "Descargar lista (CSV)",
                lista.drop(columns=["whatsapp"]).to_csv(index=False).encode("utf-8-sig"),
                file_name="clientes_a_recuperar.csv", mime="text/csv",
            )

    st.write("")
    izquierda, derecha = st.columns(2)

    with izquierda:
        with tarjeta("Qué servicios destacar", "Euros por hora de trabajo (precio entre duración, sin contar productos)", alto=490):
            rentabilidad = an.rentabilidad_servicios(datos)
            maximo = rentabilidad["euros_por_hora"].max() if not rentabilidad.empty else 0
            lista_barras([(r["nombre"], f"{r['euros_por_hora']:.0f} €/h", fraccion(r["euros_por_hora"], maximo), "") for _, r in rentabilidad.iterrows()])

    with derecha:
        with tarjeta("Huecos que conviene llenar", "Franjas con menos citas (sin contar la última hora): candidatas a una promoción", alto=490):
            mapa_flojo = an.mapa_de_horas(datos, desde, hasta)
            if mapa_flojo.empty:
                st.caption("Sin citas en este periodo.")
            else:
                mapa_flojo = mapa_flojo[mapa_flojo["hora"] < mapa_flojo.groupby("dia_num")["hora"].transform("max")]
                peores = mapa_flojo.sort_values(["citas", "dia_num", "hora"]).head(6)
                lista_barras([
                    (f"{r['dia'].capitalize()} {int(r['hora'])}:00", f"{int(r['citas'])} " + ("cita" if int(r["citas"]) == 1 else "citas"), fraccion(r["citas"], max(mapa_flojo["citas"].max(), 1)), "")
                    for _, r in peores.iterrows()
                ], color="rojo")


# Alturas mínimas de las tarjetas (una sola regla CSS al final de la página).
if _alturas:
    st.markdown(
        "<style>" + "".join(f".st-key-{clave} {{ min-height: {alto}px; }}" for clave, alto in _alturas.items()) + "</style>",
        unsafe_allow_html=True,
    )
