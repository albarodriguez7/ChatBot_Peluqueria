"""
Cálculo de estadísticas para el panel de la propietaria.

Son funciones puras sobre DataFrames (sin Streamlit), para poder probarlas.
Criterios que conviene conocer:

- Ingresos y visitas salen de ventas.csv (lo cobrado).
- Costes = gastos.csv + compras.csv + nóminas. Las compras a proveedores no
  se solapan con gastos.csv (allí van alquiler, suministros, marketing...).
- Las nóminas se reparten por días dentro de cada mes.
- Ocupación, mapa de horas, origen de reservas y cancelaciones salen de las citas.
"""

import pandas as pd

from reservas import config, db
from reservas.disponibilidad import cargar_empleados, cargar_servicios

DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
ORIGEN_ETIQUETAS = {"asistente": "Web (asistente)", "telefono": "Teléfono", "tienda": "En la tienda"}

DIAS_EN_RIESGO = 60     # sin venir desde hace más de 60 días
DIAS_PERDIDA = 120      # sin venir desde hace más de 120 días

COLUMNAS = {
    "ventas": ["id_venta", "fecha", "id_cliente", "servicio", "empleado", "importe"],
    "gastos": ["id_gasto", "fecha", "categoria", "concepto", "importe"],
    "compras": ["id_compra", "fecha", "proveedor", "producto", "cantidad", "importe"],
}


# ============================================================
# CARGA
# ============================================================

def _csv(nombre):
    ruta = config.DATA_DIR / f"{nombre}.csv"

    if ruta.exists():
        df = pd.read_csv(ruta, encoding="utf-8-sig")
    else:
        df = pd.DataFrame(columns=COLUMNAS[nombre])

    df["fecha"] = pd.to_datetime(df["fecha"])

    return df


def cargar_datos():
    clientes = db.leer("SELECT * FROM clientes")
    clientes["fecha_alta"] = pd.to_datetime(clientes["fecha_alta"])

    citas = db.leer("SELECT * FROM citas")
    citas["fecha"] = pd.to_datetime(citas["fecha"])

    return {
        "ventas": _csv("ventas"),
        "gastos": _csv("gastos"),
        "compras": _csv("compras"),
        "empleados": cargar_empleados(),
        "servicios": cargar_servicios(),
        "clientes": clientes,
        "citas": citas,
    }


def filtrar(df, desde, hasta, columna="fecha"):
    if df.empty:
        return df

    return df[(df[columna] >= pd.Timestamp(desde)) & (df[columna] <= pd.Timestamp(hasta))]


def periodo_anterior(desde, hasta):
    """Periodo de la misma duración justo antes."""
    desde, hasta = pd.Timestamp(desde), pd.Timestamp(hasta)
    dias = (hasta - desde).days + 1

    return desde - pd.Timedelta(days=dias), desde - pd.Timedelta(days=1)


# ============================================================
# DINERO
# ============================================================

def _meses_prorrateados(desde, hasta):
    """Cuántos 'meses de nómina' hay entre dos fechas, contando cada mes por sus días."""
    desde, hasta = pd.Timestamp(desde).normalize(), pd.Timestamp(hasta).normalize()

    if hasta < desde:
        return 0.0

    total = 0.0

    for mes in pd.period_range(desde, hasta, freq="M"):
        inicio = max(desde, mes.start_time.normalize())
        fin = min(hasta, mes.end_time.normalize())
        total += ((fin - inicio).days + 1) / mes.days_in_month

    return total


def nominas(empleados, desde, hasta):
    return float(empleados["pago_mes"].sum()) * _meses_prorrateados(desde, hasta)


def kpis(datos, desde, hasta):
    ventas = filtrar(datos["ventas"], desde, hasta)
    gastos = float(filtrar(datos["gastos"], desde, hasta)["importe"].sum())
    compras = float(filtrar(datos["compras"], desde, hasta)["importe"].sum())
    pagos = nominas(datos["empleados"], desde, hasta)

    ingresos = float(ventas["importe"].sum())
    servicios = len(ventas)
    costes = gastos + compras + pagos
    beneficio = ingresos - costes

    return {
        "ingresos": ingresos,
        "servicios": servicios,
        "ticket_medio": ingresos / servicios if servicios else 0.0,
        "clientes_atendidos": int(ventas["id_cliente"].nunique()),
        "gastos": gastos,
        "compras": compras,
        "nominas": pagos,
        "costes": costes,
        "beneficio": beneficio,
        "margen": beneficio / ingresos if ingresos else 0.0,
    }


def serie_mensual(datos, desde, hasta):
    """Ingresos, costes y beneficio por mes."""
    filas = []

    for mes in pd.period_range(pd.Timestamp(desde), pd.Timestamp(hasta), freq="M"):
        inicio = max(pd.Timestamp(desde), mes.start_time.normalize())
        fin = min(pd.Timestamp(hasta), mes.end_time.normalize())

        k = kpis(datos, inicio, fin)
        filas.append({
            "mes": mes.start_time,
            "ingresos": k["ingresos"],
            "costes": k["costes"],
            "beneficio": k["beneficio"],
        })

    return pd.DataFrame(filas, columns=["mes", "ingresos", "costes", "beneficio"])


def ingresos_por_servicio(datos, desde, hasta):
    ventas = filtrar(datos["ventas"], desde, hasta)

    if ventas.empty:
        return pd.DataFrame(columns=["servicio", "ingresos", "servicios", "ticket_medio"])

    return (
        ventas.groupby("servicio")
        .agg(ingresos=("importe", "sum"), servicios=("importe", "size"))
        .assign(ticket_medio=lambda d: d["ingresos"] / d["servicios"])
        .sort_values("ingresos", ascending=False)
        .reset_index()
    )


def ingresos_por_profesional(datos, desde, hasta):
    ventas = filtrar(datos["ventas"], desde, hasta)

    if ventas.empty:
        return pd.DataFrame(columns=["empleado", "ingresos", "servicios", "ticket_medio"])

    return (
        ventas.groupby("empleado")
        .agg(ingresos=("importe", "sum"), servicios=("importe", "size"))
        .assign(ticket_medio=lambda d: d["ingresos"] / d["servicios"])
        .sort_values("ingresos", ascending=False)
        .reset_index()
    )


def costes_por_categoria(datos, desde, hasta):
    gastos = filtrar(datos["gastos"], desde, hasta)
    partes = gastos.groupby("categoria")["importe"].sum().to_dict() if not gastos.empty else {}

    compras = float(filtrar(datos["compras"], desde, hasta)["importe"].sum())
    if compras:
        partes["Compras a proveedores"] = compras

    partes["Nóminas"] = nominas(datos["empleados"], desde, hasta)

    return (
        pd.DataFrame({"categoria": list(partes), "importe": list(partes.values())})
        .sort_values("importe", ascending=False)
        .reset_index(drop=True)
    )


def rentabilidad_servicios(datos):
    """Euros por hora de trabajo de cada servicio (precio / duración)."""
    servicios = datos["servicios"].copy()
    servicios["euros_por_hora"] = servicios["precio"] / servicios["duracion_minutos"] * 60

    return servicios.sort_values("euros_por_hora", ascending=False).reset_index(drop=True)


# ============================================================
# CLIENTES
# ============================================================

def resumen_clientes(datos, hoy):
    """Una fila por cliente con su historial y su segmento."""
    hoy = pd.Timestamp(hoy)
    ventas = datos["ventas"]

    if ventas.empty:
        agregado = pd.DataFrame(
            columns=["id_cliente", "visitas", "gasto_total", "primera_visita", "ultima_visita"]
        )
        ultimo = pd.DataFrame(columns=["id_cliente", "ultimo_servicio"])
    else:
        agregado = ventas.groupby("id_cliente").agg(
            visitas=("importe", "size"),
            gasto_total=("importe", "sum"),
            primera_visita=("fecha", "min"),
            ultima_visita=("fecha", "max"),
        ).reset_index()

        ultimo = (
            ventas.sort_values("fecha")
            .groupby("id_cliente")
            .tail(1)[["id_cliente", "servicio"]]
            .rename(columns={"servicio": "ultimo_servicio"})
        )

    resumen = (
        datos["clientes"][["id_cliente", "nombre", "telefono", "fecha_alta"]]
        .merge(agregado, on="id_cliente", how="left")
        .merge(ultimo, on="id_cliente", how="left")
    )

    resumen["visitas"] = resumen["visitas"].fillna(0).astype(int)
    resumen["gasto_total"] = resumen["gasto_total"].fillna(0.0)
    resumen["primera_visita"] = pd.to_datetime(resumen["primera_visita"])
    resumen["ultima_visita"] = pd.to_datetime(resumen["ultima_visita"])
    resumen["dias_desde_ultima"] = (hoy - resumen["ultima_visita"]).dt.days

    def segmento(fila):
        if fila["visitas"] == 0:
            return "Sin visitas"
        if fila["dias_desde_ultima"] > DIAS_PERDIDA:
            return "Perdida"
        if fila["dias_desde_ultima"] > DIAS_EN_RIESGO:
            return "En riesgo"
        return "Nueva" if fila["visitas"] == 1 else "Recurrente"

    resumen["segmento"] = resumen.apply(segmento, axis=1)

    con_visitas = resumen[resumen["visitas"] > 0]
    umbral = con_visitas["gasto_total"].quantile(0.8) if not con_visitas.empty else float("inf")
    resumen["vip"] = (resumen["visitas"] >= 3) & (resumen["gasto_total"] >= umbral)

    return resumen


def tasa_repeticion(resumen):
    """De los clientes que han venido alguna vez, cuántos han vuelto (2 o más visitas)."""
    con_visitas = resumen[resumen["visitas"] > 0]

    if con_visitas.empty:
        return 0.0

    return float((con_visitas["visitas"] >= 2).mean())


def nuevos_por_mes(datos, desde, hasta):
    clientes = filtrar(datos["clientes"], desde, hasta, columna="fecha_alta")
    meses = pd.period_range(pd.Timestamp(desde), pd.Timestamp(hasta), freq="M")

    conteo = clientes.groupby(clientes["fecha_alta"].dt.to_period("M")).size() if not clientes.empty else pd.Series(dtype=int)

    return pd.DataFrame({
        "mes": [m.start_time for m in meses],
        "clientes_nuevos": [int(conteo.get(m, 0)) for m in meses],
    })


def lista_reactivacion(resumen, minimo_dias=DIAS_EN_RIESGO):
    """Clientes que dejaron de venir, ordenados por lo que gastaron."""
    lista = resumen[
        (resumen["visitas"] > 0) & (resumen["dias_desde_ultima"] > minimo_dias)
    ]

    return (
        lista.sort_values("gasto_total", ascending=False)
        [["nombre", "telefono", "dias_desde_ultima", "ultima_visita", "ultimo_servicio", "visitas", "gasto_total"]]
        .reset_index(drop=True)
    )


# ============================================================
# AGENDA Y OCUPACIÓN
# ============================================================

def _minutos(hora):
    h, m = map(int, str(hora).split(":"))
    return h * 60 + m


def ocupacion(datos, desde, hasta, hoy):
    """Minutos reservados frente a minutos de apertura, por profesional. Solo hasta hoy."""
    hasta = min(pd.Timestamp(hasta), pd.Timestamp(hoy))
    desde = pd.Timestamp(desde)

    minutos_abierto = 0
    if hasta >= desde:
        for dia in pd.date_range(desde, hasta):
            horario = config.HORARIOS_NEGOCIO.get(dia.weekday())
            if horario:
                minutos_abierto += _minutos(horario[1]) - _minutos(horario[0])

    citas = filtrar(datos["citas"], desde, hasta)
    citas = citas[citas["estado"] == "confirmada"] if not citas.empty else citas

    filas = []

    for _, e in datos["empleados"].iterrows():
        propias = citas[citas["id_empleado"] == int(e["id_empleado"])] if not citas.empty else citas
        reservados = int(sum(_minutos(f) - _minutos(i) for i, f in zip(propias["hora_inicio"], propias["hora_fin"]))) if not propias.empty else 0

        filas.append({
            "empleado": e["nombre"],
            "minutos_reservados": reservados,
            "minutos_disponibles": minutos_abierto,
            "ocupacion": reservados / minutos_abierto if minutos_abierto else 0.0,
        })

    return pd.DataFrame(filas)


def mapa_de_horas(datos, desde, hasta):
    """Número de citas por día de la semana y hora de inicio (rejilla completa, con ceros)."""
    citas = filtrar(datos["citas"], desde, hasta)
    citas = citas[citas["estado"] == "confirmada"] if not citas.empty else citas

    conteo = {}
    if not citas.empty:
        for fecha, hora in zip(citas["fecha"], citas["hora_inicio"]):
            clave = (fecha.weekday(), _minutos(hora) // 60)
            conteo[clave] = conteo.get(clave, 0) + 1

    filas = []
    for dia, horario in sorted(config.HORARIOS_NEGOCIO.items()):
        if not horario:
            continue
        for hora in range(_minutos(horario[0]) // 60, (_minutos(horario[1]) - 1) // 60 + 1):
            filas.append({
                "dia": DIAS_SEMANA[dia], "dia_num": dia, "hora": hora,
                "citas": conteo.get((dia, hora), 0),
            })

    return pd.DataFrame(filas)


def origen_reservas(datos, desde, hasta):
    citas = filtrar(datos["citas"], desde, hasta)
    citas = citas[citas["estado"] == "confirmada"] if not citas.empty else citas

    if citas.empty:
        return pd.DataFrame(columns=["origen", "citas"])

    return (
        citas.assign(origen=citas["origen"].map(lambda o: ORIGEN_ETIQUETAS.get(o, o)))
        .groupby("origen").size().rename("citas").reset_index()
        .sort_values("citas", ascending=False)
    )


def tasa_cancelacion(datos, desde, hasta):
    citas = filtrar(datos["citas"], desde, hasta)

    if citas.empty:
        return 0.0

    return float((citas["estado"] == "cancelada").mean())


# ============================================================
# MARKETING
# ============================================================

def marketing_mensual(datos, desde, hasta):
    """Gasto en marketing, clientes nuevos y coste por cliente nuevo, por mes."""
    gastos = datos["gastos"]
    gastos = gastos[gastos["categoria"] == "Marketing"] if not gastos.empty else gastos
    nuevos = nuevos_por_mes(datos, desde, hasta)

    filas = []

    for _, fila in nuevos.iterrows():
        mes = fila["mes"]
        fin = mes + pd.offsets.MonthEnd(0)
        gasto = float(filtrar(gastos, mes, fin)["importe"].sum())
        n = int(fila["clientes_nuevos"])

        filas.append({
            "mes": mes,
            "gasto_marketing": gasto,
            "clientes_nuevos": n,
            "coste_por_cliente_nuevo": gasto / n if n else None,
        })

    return pd.DataFrame(filas)


def ideas(datos, desde, hasta, hoy):
    """
    Observaciones automáticas a partir de los números. Son pistas para decidir,
    no conclusiones: dicen de dónde salen para poder comprobarlas.
    """
    frases = []

    resumen = resumen_clientes(datos, hoy)
    lista = lista_reactivacion(resumen)

    if len(lista):
        frases.append(
            f"{len(lista)} clientes llevan más de {DIAS_EN_RIESGO} días sin venir y sumaron "
            f"{lista['gasto_total'].sum():,.0f} € en total. Una campaña de reactivación por WhatsApp "
            f"es lo más directo (pestaña Marketing)."
        )

    mapa = mapa_de_horas(datos, desde, hasta)
    # La última hora de cada día casi no admite servicios largos: no cuenta como "hueco flojo".
    if not mapa.empty:
        mapa = mapa[mapa["hora"] < mapa.groupby("dia_num")["hora"].transform("max")]
    if not mapa.empty and mapa["citas"].sum() > 0:
        flojo = mapa.sort_values(["citas", "dia_num", "hora"]).iloc[0]
        frases.append(
            f"La franja con menos citas es {flojo['dia']} a las {int(flojo['hora'])}:00 "
            f"({int(flojo['citas'])} en el periodo): buena candidata para una promoción."
        )

    servicios = rentabilidad_servicios(datos)
    if not servicios.empty:
        mejor = servicios.iloc[0]
        frases.append(
            f"El servicio que más deja por hora de trabajo es {mejor['nombre']} "
            f"({mejor['euros_por_hora']:,.0f} €/h). Merece protagonismo en redes."
        )

    rep = tasa_repeticion(resumen)
    if rep:
        frases.append(f"El {rep:.0%} de los clientes que han venido alguna vez ha vuelto.")

    return frases
