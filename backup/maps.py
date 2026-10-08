"""
    Gestionar el mapa para el analisis
"""

from scripts.config import mexico_map, PRELOAD_MAP, DATA_FOLDERS
from scripts.download import download
import os


if not os.path.exists(PRELOAD_MAP):
    download(mexico_map, "Mexico.zip", DATA_FOLDERS['external'] / "inegi")