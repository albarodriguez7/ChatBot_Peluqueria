"""
Configuración única del negocio.

Aquí viven los datos que antes estaban repartidos entre el código
y el documento del RAG: horario, zona horaria y rutas de datos.
Si cambia el horario, se cambia SOLO aquí (y en documentos_negocio/negocio.txt
para que el RAG lo cuente igual).
"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parents[2]

# Los datos maestros (servicios, empleados, ventas...) siguen en CSV.
# Los datos que cambian con cada reserva (clientes, citas) viven en SQLite:
# datos_negocio/studio_alba.db
# Los módulos leen config.DATA_DIR en cada llamada (no lo copian al importar),
# así los tests pueden apuntarlo a una carpeta temporal.
DATA_DIR = BASE_DIR / "datos_negocio"

ZONA_HORARIA = ZoneInfo("Europe/Madrid")

# 0 = lunes ... 6 = domingo. None = cerrado.
HORARIOS_NEGOCIO = {
    0: ("09:30", "19:30"),
    1: ("09:30", "19:30"),
    2: ("09:30", "19:30"),
    3: ("09:30", "19:30"),
    4: ("09:30", "19:30"),
    5: ("09:30", "14:00"),
    6: None,
}

INTERVALO_MINUTOS = 30

def ahora() -> datetime:
    """Fecha y hora actuales en Madrid (sin zona, para comparar con las citas)."""
    return datetime.now(ZONA_HORARIA).replace(tzinfo=None)
