"""
Sincroniza a mano los calendarios de Google con la base de datos.

    poetry run python app/sincronizar_calendario.py             # sincroniza
    poetry run python app/sincronizar_calendario.py --comprobar # solo comprueba el acceso

La aplicación ya sincroniza sola tras cada cambio. Este script sirve para la
primera carga, para comprobar la configuración y, si quieres una red de seguridad,
para programarlo cada 15-30 minutos (por ejemplo con el Programador de tareas de Windows).
"""

import argparse
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

from reservas import calendario  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--comprobar", action="store_true", help="solo comprobar el acceso a los calendarios")
    argumentos = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    if not calendario.habilitado():
        print(
            "Google Calendar no está configurado.\n"
            "Comprueba en el .env: GOOGLE_SERVICE_ACCOUNT_FILE (y que el archivo existe) "
            "y GCAL_EMPLEADO_1, GCAL_EMPLEADO_2..."
        )
        return 1

    if argumentos.comprobar:
        correcto = True
        for nombre, ok, mensaje in calendario.comprobar_acceso():
            print(f"{'OK ' if ok else 'ERROR'} {nombre}: {mensaje}")
            correcto = correcto and ok
        return 0 if correcto else 1

    resumen = calendario.sincronizar()
    print(
        f"Creados: {resumen['creados']} | Actualizados: {resumen['actualizados']} "
        f"| Borrados: {resumen['borrados']}"
    )

    for error in resumen["errores"]:
        print(f"ERROR {error}")

    return 1 if resumen["errores"] else 0


if __name__ == "__main__":
    sys.exit(main())
