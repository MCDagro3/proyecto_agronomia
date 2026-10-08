"""
    Configuraciones Generales del Proyecto de Agronomia.
"""
from yarl import URL
from pathlib import Path


ROOT = list(Path(__file__).resolve().parents)[1]
DATA_DIR = ROOT / "data"


def save_path(folderfinal, **kwargs)-> Path:
    block_folder = kwargs.get("folder", "data")
    source = kwargs.get("source", "DGSIAP")
    assert source in data_sources, f"Revisa tus fuentes en {ROOT}"
    file_to = ROOT / block_folder / folderfinal / source
    return file_to
    

# Fuentes de datos utilizadas
data_sources = ['DGSIAP','INEGI','OPENMETEO','DATAMEXICO']

# Las etapas de nuestros datos.
## El orden de la lista expone los pasos del procesamiento.
### pure: Descargados
### raw: Legibles.
### interm: Preprocesamiento.
### process: Limpios

data_folders = ["pure", "raw", "interm", "process"]

# Banco de URLS organizadas por fuente

source_links = {"DGSIAP": {
                    "request": URL("https://nube.agricultura.gob.mx/datosAbiertos/"),
                    "download":URL("https://nube.agricultura.gob.mx/index.php"),
                    "avance": URL("https://nube.agricultura.gob.mx/avance_agricola/"),
                    "agroprograma": URL("https://nube.agricultura.gob.mx/agroprograma/")},
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

# Paremtros de las bases de datos.
## DGSIAP
### Elegir entre la producción agricola y ganadera
info = {
        "Agricola": "Agricola.php",
        "Pecuaria": "Pecuario.php",
    }
### Se elige la base de datos a utilizar
dgsiap_info = info['Agricola']


# Datos Publicos precargados para acelear el analisis de datos
PRELOADS = {"MAPA GENERAL": ROOT / "preload" / "mexico_agro.zip"}




