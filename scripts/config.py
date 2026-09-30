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
DATA_FOLDERS = {"external": DATA_DIR / "external",
                "raw": DATA_DIR / "raw",
                "interm": DATA_DIR / "interim",
                "process": DATA_DIR / "processed",
}

# Fuentes de Datos
## DGSIAP
dgsiap_source = yarl.URL("https://nube.agricultura.gob.mx")
dgsiap_page = dgsiap_source / "datosAbiertos/"
dgsiap = dgsiap_source / "index.php"

## DATA MEXICO
datamexico = yarl.URL("https://www.economia.gob.mx/apidatamexico/tesseract/data.jsonrecords")

