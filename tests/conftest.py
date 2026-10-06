import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "app"))

from reservas import config  # noqa: E402


@pytest.fixture(autouse=True)
def datos_temporales(tmp_path, monkeypatch):
    """Cada test trabaja con una copia de los datos: nunca toca los reales."""
    destino = tmp_path / "datos_negocio"
    # Solo los CSV: si existe la base de datos real, no se copia.
    shutil.copytree(
        RAIZ / "datos_negocio", destino,
        ignore=shutil.ignore_patterns("*.db", "*.db-*", "citas_huerfanas.csv"),
    )
    monkeypatch.setattr(config, "DATA_DIR", destino)
    return destino
