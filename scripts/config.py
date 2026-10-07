import yarl
from pathlib import Path
import os

# Ubicación de los archivos descargados
## Definimos la ruta principal. En este caso la ruta de la carpeta donde se encuentra el proyexto.
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

DATA_DIR = get_project_root() / "data"

# Definimos las etapas de datos que vamos a usar.
data_steps = [folder for folder in os.listdir(DATA_DIR) if not folder.startswith(".")]

# Definimos las fuentes de información a utilziar 
data_sources = ["inegi", "datamexico", "dgsiap", "openmeteo"]

def file_to(data_level, source, data_folder = DATA_DIR, valid_levels = data_steps, valid_sources = data_sources):
    assert data_level in valid_levels
    assert source in valid_sources
    filepath = data_folder / data_level / source
    return filepath


LOG_DIR = get_project_root() / "docs"



# Mapa de México precargado para evitar la descarga durante el analisis.
PRELOAD_MEXICO = DATA_DIR / "docs" / "mexico_agro.zip"



# Fuentes de Datos
## DGSIAP
dgsiap_source = yarl.URL("https://nube.agricultura.gob.mx")
dgsiap_page = dgsiap_source / "datosAbiertos/"
dgsiap_api = dgsiap_source / "index.php"


## DATA MEXICO
datamexico = yarl.URL("https://www.economia.gob.mx/apidatamexico/tesseract/data.jsonrecords")


# Visualización
## Mapa de la Republica Méxicana con Estados y Municipios. Para descarga
inegi_mexico = "https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/geografia/marcogeo/794551196649/mg_integrado_encuesta_intercensal_2025.zip"
mexico_map = yarl.URL(inegi_mexico)