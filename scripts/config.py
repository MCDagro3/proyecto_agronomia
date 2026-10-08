"""
    Configuraciones Generales del Proyecto de Agronomia.
"""
from yarl import URL
from pathlib import Path


# Primero definimos la ruta referencia del projecto
ROOT = get_project_root()

def get_project_root() -> Path:
    """
    Detecta automáticamente la raíz del proyecto.
    Funciona tanto en scripts como en Jupyter notebooks.
    """
    try:
        current_path = Path(__file__).resolve()
    except NameError:
        current_path = Path.cwd()
    
    for parent in [current_path] + list(current_path.parents):
        if (parent / "data").is_dir():
            return parent
    return Path.cwd()


def save_path(folderfinal, **kwargs)-> Path:
    block_folder = kwargs.get("folder", "data")
    source = kwargs.get("source", "DGSIAP")
    assert source in data_sources, f"Revisa tus fuentes en {ROOT}"
    file_to = ROOT / block_folder / folderfinal / source
    return file_to
    

# Fuentes de datos utilizadas
data_sources = ['DGSIAP','INEGI','OPENMETEO','DATAMEXICO']

# Las etapas de nuestros datos
data_folders = ["pure", "raw", "interm", "process"]

# Banco de URLS organizadas por fuente

source_links = {"DGSIAP": {
                    "request": URL("https://nube.agricultura.gob.mx/datosAbiertos/"),
                    "download":URL("https://nube.agricultura.gob.mx/datosAbiertos/index.php")},
                "DATAMEXICO": {
                    "request": None,
                    "download":URL("https://www.economia.gob.mx/apidatamexico/tesseract/data.jsonrecords")},
                "OPENMETEO":{
                    "request": None,
                    "download": None},
                "INEGI":{"MAPA GENERAL":{
                    "request": None,
                    "download": URL("https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/geografia/marcogeo/794551196649/mg_integrado_encuesta_intercensal_2025.zip")}
                    }
}

# Datos Publicos precargados para acelear el analisis de datos
PRELOADS = {"MAPA GENERAL": ROOT / preload / "mexico_agro.zip"}




