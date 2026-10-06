"""
Genera datos de demostración para el panel de la propietaria.

    poetry run python app/generar_datos_demo.py            # 6 meses
    poetry run python app/generar_datos_demo.py --meses 9

Qué hace:
  1. Guarda una copia de seguridad (carpeta datos_negocio/backup_<fecha>) con
     ventas.csv, gastos.csv, compras.csv y la base de datos.
  2. Añade clientes de demostración (teléfonos que empiezan por 000, que no existen).
  3. Sustituye ventas.csv, gastos.csv y compras.csv por varios meses de historial.
  4. Añade a la base de datos las citas pasadas que corresponden a cada venta
     (más algunas canceladas), con ids desde 1000.

Se puede repetir: vuelve a generar el historial pasado sin duplicar clientes.
Los datos son inventados y solo sirven para enseñar el panel. No toca las
citas futuras ni los bloqueos.
"""

import argparse
import random
import shutil
import sqlite3
from datetime import timedelta

import pandas as pd
from dotenv import load_dotenv

from reservas import config, db
from reservas.disponibilidad import cargar_empleados, cargar_servicios, hora_a_minutos, minutos_a_hora

PREFIJO_TELEFONO_DEMO = "000"
PRIMER_ID_CITA_DEMO = 1000

NOMBRES = [
    "Lucía", "Sofía", "María", "Paula", "Carmen", "Laura", "Marta", "Elena", "Ana", "Sara",
    "Claudia", "Irene", "Nuria", "Cristina", "Beatriz", "Alicia", "Rocío", "Teresa", "Pilar",
    "Andrea", "Julia", "Silvia", "Raquel", "Patricia", "Inés", "Natalia", "Diana", "Lorena",
    "Álvaro", "Javier", "Daniel", "Pablo", "Sergio", "Adrián",
]
APELLIDOS = [
    "García", "Martínez", "López", "Sánchez", "Pérez", "Gómez", "Fernández", "Díaz", "Ruiz",
    "Hernández", "Jiménez", "Moreno", "Muñoz", "Álvarez", "Romero", "Alonso", "Gutiérrez",
    "Navarro", "Torres", "Domínguez", "Vázquez", "Ramos", "Gil", "Serrano", "Blanco", "Molina",
    "Castro", "Ortega", "Rubio", "Marín",
]

PESO_SERVICIO = {
    "Corte mujer": 22, "Corte hombre": 10, "Corte + peinado": 14, "Lavado + peinado": 12,
    "Tinte": 10, "Mechas": 6, "Balayage": 4, "Tratamiento capilar": 8,
    "Color + corte": 8, "Mechas + corte": 5,
}

# Los martes y los lunes son más flojos; viernes y sábado, los más llenos.
PESO_DIA = {0: 0.8, 1: 0.5, 2: 0.8, 3: 1.0, 4: 1.3, 5: 1.4}

PRODUCTOS = [
    ("Distribuciones Hair", "Champú profesional", 8.0),
    ("Distribuciones Hair", "Mascarilla capilar", 9.0),
    ("Beauty Pro", "Tinte profesional", 7.0),
    ("Beauty Pro", "Decolorante", 11.0),
    ("Beauty Pro", "Oxidante", 4.0),
    ("Beauty Pro", "Guantes y material", 5.5),
]

MARKETING_POR_MES = [120, 150, 300, 120, 180, 250]     # se repite; el mes 3 tiene campaña


def _copia_de_seguridad():
    carpeta = config.DATA_DIR / f"backup_{config.ahora():%Y%m%d_%H%M%S}"
    carpeta.mkdir(parents=True, exist_ok=True)

    for nombre in ("ventas", "gastos", "compras"):
        origen = config.DATA_DIR / f"{nombre}.csv"
        if origen.exists():
            shutil.copy2(origen, carpeta / origen.name)

    origen = db.conectar()
    destino = sqlite3.connect(carpeta / "studio_alba.db")
    try:
        origen.backup(destino)
    finally:
        destino.close()
        origen.close()

    return carpeta


def _elegir_servicio(azar, servicios):
    nombres = list(servicios["nombre"])
    pesos = [PESO_SERVICIO.get(n, 5) for n in nombres]
    return azar.choices(nombres, weights=pesos)[0]


def _crear_clientes(azar, con, inicio, hoy, n_clientes):
    """Añade clientes de demo si aún no existen. Devuelve [(id, fecha_alta)] de todos los clientes."""
    ya = con.execute(
        "SELECT COUNT(*) FROM clientes WHERE telefono LIKE ?", (PREFIJO_TELEFONO_DEMO + "%",)
    ).fetchone()[0]

    if not ya:
        meses = int(round((pd.Timestamp(hoy) - pd.Timestamp(inicio)).days / 30.4))
        nuevos_por_mes = [
            round(8 + MARKETING_POR_MES[i % len(MARKETING_POR_MES)] / 20) for i in range(meses)
        ]
        antiguos = max(20, n_clientes - sum(nuevos_por_mes))

        altas = [
            inicio - timedelta(days=azar.randint(1, 365)) for _ in range(antiguos)
        ]
        for i, cantidad in enumerate(nuevos_por_mes):
            primero = (pd.Timestamp(inicio) + pd.DateOffset(months=i)).date()
            ultimo = min((pd.Timestamp(primero) + pd.DateOffset(months=1) - pd.Timedelta(days=1)).date(),
                         hoy - timedelta(days=1))
            dias = max((ultimo - primero).days, 0)
            altas += [primero + timedelta(days=azar.randint(0, dias)) for _ in range(cantidad)]

        combinaciones = [(n, a) for n in NOMBRES for a in APELLIDOS]
        azar.shuffle(combinaciones)

        siguiente = con.execute("SELECT COALESCE(MAX(id_cliente), 0) + 1 FROM clientes").fetchone()[0]

        for numero, alta in enumerate(altas, start=1):
            nombre, apellido = combinaciones[numero % len(combinaciones)]
            email = (
                f"{nombre}.{apellido}".lower().replace("á", "a").replace("é", "e").replace("í", "i")
                .replace("ó", "o").replace("ú", "u") + "@example.com"
                if azar.random() < 0.3 else ""
            )
            con.execute(
                "INSERT INTO clientes (id_cliente, nombre, telefono, email, fecha_alta) VALUES (?,?,?,?,?)",
                (siguiente, f"{nombre} {apellido}", f"{PREFIJO_TELEFONO_DEMO}{numero:06d}", email, str(alta)),
            )
            siguiente += 1

    return [
        (int(f["id_cliente"]), pd.to_datetime(f["fecha_alta"]).date())
        for f in con.execute("SELECT id_cliente, fecha_alta FROM clientes ORDER BY id_cliente").fetchall()
        if f["fecha_alta"]
    ]


def _simular_visitas(azar, clientes, servicios, ids_empleados, ocupado, inicio, hoy):
    duracion = dict(zip(servicios["nombre"], servicios["duracion_minutos"]))
    precio = dict(zip(servicios["nombre"], servicios["precio"]))

    def colocar(fecha, minutos, preferido):
        for desplazamiento in range(4):
            dia = fecha + timedelta(days=desplazamiento)
            horario = config.HORARIOS_NEGOCIO.get(dia.weekday())
            if not horario or dia >= hoy:
                continue

            apertura, cierre = hora_a_minutos(horario[0]), hora_a_minutos(horario[1])
            orden = [preferido] + [e for e in ids_empleados if e != preferido]

            for empleado in orden:
                ocupadas = ocupado.setdefault((dia, empleado), [])
                for _ in range(14):
                    ini = azar.randrange(apertura, cierre - minutos + 1, 15) if cierre - minutos >= apertura else None
                    if ini is None:
                        break
                    fin = ini + minutos
                    if all(fin <= i or ini >= f for i, f in ocupadas):
                        ocupadas.append((ini, fin))
                        return dia, empleado, ini, fin
        return None

    visitas = []
    dias_peso = list(PESO_DIA)
    pesos = [PESO_DIA[d] for d in dias_peso]

    for id_cliente, alta in clientes:
        if alta >= hoy:
            continue

        frecuencia = azar.randint(60, 100) if azar.random() < 0.25 else azar.randint(28, 50)
        favorito = _elegir_servicio(azar, servicios)
        empleado_fav = azar.choice(ids_empleados)
        abandona = inicio + timedelta(days=azar.randint(0, (hoy - inicio).days)) if azar.random() < 0.2 else None

        fecha = max(alta + timedelta(days=azar.randint(0, 10)), inicio + timedelta(days=azar.randint(0, frecuencia)))

        while fecha < hoy:
            if abandona and fecha > abandona:
                break

            lunes = fecha - timedelta(days=fecha.weekday())
            fecha_pedida = max(lunes + timedelta(days=azar.choices(dias_peso, weights=pesos)[0]), inicio)
            servicio = favorito if azar.random() < 0.7 else _elegir_servicio(azar, servicios)
            preferido = empleado_fav if azar.random() < 0.7 else azar.choice(ids_empleados)

            hueco = colocar(fecha_pedida, int(duracion[servicio]), preferido)
            if hueco:
                dia, empleado, ini, fin = hueco
                visitas.append({
                    "fecha": dia, "id_cliente": id_cliente, "servicio": servicio,
                    "importe": float(precio[servicio]), "empleado": empleado, "ini": ini, "fin": fin,
                })

            fecha += timedelta(days=max(14, frecuencia + azar.randint(-7, 10)))

    return sorted(visitas, key=lambda v: (v["fecha"], v["ini"]))


def _gastos_y_compras(azar, inicio, hoy):
    gastos, compras = [], []

    for i, mes in enumerate(pd.period_range(inicio, hoy, freq="M")):
        def dia(n):
            return mes.start_time.date() + timedelta(days=n - 1)

        previstos = [
            (2, "Alquiler", "Local", 850),
            (4, "Suministros", "Electricidad y agua", azar.randint(130, 175)),
            (6, "Marketing", "Publicidad Instagram", MARKETING_POR_MES[i % len(MARKETING_POR_MES)]),
            (10, "Software", "Sistema de reservas", 45),
            (24, "Limpieza", "Productos de limpieza", azar.randint(45, 65)),
        ]
        for d, categoria, concepto, importe in previstos:
            if dia(d) <= hoy:
                gastos.append({"fecha": dia(d), "categoria": categoria, "concepto": concepto, "importe": importe})

        for _ in range(azar.randint(3, 5)):
            proveedor, producto, unitario = azar.choice(PRODUCTOS)
            cantidad = azar.randint(6, 20)
            fecha = dia(azar.randint(1, mes.days_in_month))
            if fecha <= hoy:
                compras.append({
                    "fecha": fecha, "proveedor": proveedor, "producto": producto,
                    "cantidad": cantidad, "importe": round(cantidad * unitario),
                })

    return sorted(gastos, key=lambda g: g["fecha"]), sorted(compras, key=lambda c: c["fecha"])


def generar(meses=6, semilla=7, n_clientes=280, hoy=None):
    hoy = hoy or config.ahora().date()
    azar_clientes = random.Random(semilla)
    azar = random.Random(semilla + 1)     # aparte, para que repetir dé el mismo historial
    inicio = (pd.Timestamp(hoy) - pd.DateOffset(months=meses)).replace(day=1).date()

    servicios = cargar_servicios()
    empleados = cargar_empleados()
    ids_empleados = [int(i) for i in empleados["id_empleado"]]
    nombre_empleado = dict(zip(empleados["id_empleado"].astype(int), empleados["nombre"]))

    copia = _copia_de_seguridad()

    with db.transaccion() as con:
        # Se rehace el historial pasado generado antes; las citas reales y futuras no se tocan.
        con.execute(
            "DELETE FROM citas WHERE id_cita >= ? AND fecha < ?", (PRIMER_ID_CITA_DEMO, str(hoy))
        )

        clientes = _crear_clientes(azar_clientes, con, inicio, hoy, n_clientes)

        ocupado = {}
        for f in con.execute(
            "SELECT fecha, id_empleado, hora_inicio, hora_fin FROM citas WHERE estado = 'confirmada'"
        ).fetchall():
            ocupado.setdefault((pd.to_datetime(f["fecha"]).date(), f["id_empleado"]), []).append(
                (hora_a_minutos(f["hora_inicio"]), hora_a_minutos(f["hora_fin"]))
            )

        visitas = _simular_visitas(azar, clientes, servicios, ids_empleados, ocupado, inicio, hoy)

        origenes, pesos = ["asistente", "telefono", "tienda"], [0.15, 0.45, 0.40]
        id_servicio = dict(zip(servicios["nombre"], servicios["id_servicio"].astype(int)))
        duracion = dict(zip(servicios["nombre"], servicios["duracion_minutos"].astype(int)))
        id_cita = PRIMER_ID_CITA_DEMO
        canceladas = 0

        for v in visitas:
            origen = azar.choices(origenes, weights=pesos)[0]
            con.execute(
                "INSERT INTO citas (id_cita, id_cliente, id_servicio, id_empleado, fecha, hora_inicio, "
                "hora_fin, estado, origen) VALUES (?,?,?,?,?,?,?,'confirmada',?)",
                (id_cita, v["id_cliente"], id_servicio[v["servicio"]], v["empleado"], str(v["fecha"]),
                 minutos_a_hora(v["ini"]), minutos_a_hora(v["fin"]), origen),
            )
            id_cita += 1

            if azar.random() < 0.07:                      # una cita cancelada por cada ~14 realizadas
                ini = azar.randrange(hora_a_minutos("09:30"), hora_a_minutos("13:00"), 15)
                con.execute(
                    "INSERT INTO citas (id_cita, id_cliente, id_servicio, id_empleado, fecha, hora_inicio, "
                    "hora_fin, estado, origen) VALUES (?,?,?,?,?,?,?,'cancelada',?)",
                    (id_cita, v["id_cliente"], id_servicio[v["servicio"]], azar.choice(ids_empleados),
                     str(v["fecha"]), minutos_a_hora(ini), minutos_a_hora(ini + duracion[v["servicio"]]),
                     azar.choices(origenes, weights=pesos)[0]),
                )
                id_cita += 1
                canceladas += 1

    pd.DataFrame([
        {"id_venta": i, "fecha": v["fecha"], "id_cliente": v["id_cliente"], "servicio": v["servicio"],
         "empleado": nombre_empleado[v["empleado"]], "importe": v["importe"]}
        for i, v in enumerate(visitas, start=1)
    ]).to_csv(config.DATA_DIR / "ventas.csv", index=False, encoding="utf-8")

    gastos, compras = _gastos_y_compras(azar, inicio, hoy)
    pd.DataFrame([{"id_gasto": i, **g} for i, g in enumerate(gastos, start=1)]).to_csv(
        config.DATA_DIR / "gastos.csv", index=False, encoding="utf-8")
    pd.DataFrame([{"id_compra": i, **c} for i, c in enumerate(compras, start=1)]).to_csv(
        config.DATA_DIR / "compras.csv", index=False, encoding="utf-8")

    return {
        "desde": inicio, "hasta": hoy, "clientes": len(clientes), "ventas": len(visitas),
        "citas_canceladas": canceladas, "gastos": len(gastos), "compras": len(compras),
        "copia_de_seguridad": copia,
    }


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Genera datos de demostración.")
    parser.add_argument("--meses", type=int, default=6)
    parser.add_argument("--semilla", type=int, default=7, help="misma semilla, mismos datos")
    argumentos = parser.parse_args()

    r = generar(meses=argumentos.meses, semilla=argumentos.semilla)

    print(f"Datos de demostración del {r['desde']} al {r['hasta']}:")
    print(f"  {r['clientes']} clientes, {r['ventas']} servicios cobrados, {r['citas_canceladas']} citas canceladas")
    print(f"  {r['gastos']} gastos y {r['compras']} compras")
    print(f"Copia de seguridad en: {r['copia_de_seguridad']}")


if __name__ == "__main__":
    main()
