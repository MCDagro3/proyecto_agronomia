# Rutas para la construcción del mantenimiebnto del proyecto.  
from pathlib import Path
import os

# Raiz del Proyecto
ROOT = Path(__file__).parents[2]

# Fuentes de Datos
DATA_SOURCES = ["DGSIAP", "NASAPOWER", "MAPBIOMAS", "INEGI"]

# Etapas del Analisis de Datos.

DATA_LEVELS = ["pure", "raw", "preload", "processed"]

def construct_datafolder(sources = DATA_SOURCES, levels = DATA_LEVELS):
    FOLDER_DATA = ROOT / "data"
    paths = {}
    for level in levels:
        sources_levels = {}
        for source in sources:
            path = FOLDER_DATA / level / source
            os.makedirs(path, exist_ok=True)
            sources_levels[source] = path
        paths[level] = sources_levels
    return paths

datapaths = construct_datafolder()

