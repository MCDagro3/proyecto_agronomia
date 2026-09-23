import yarl
from pathlib import Path

# URLS principales
MAIN_URL = yarl.URL("https://nube.agricultura.gob.mx")

# Ubicación de los archivos descargados
## Definimos la ruta de descarga de archivos.
REF_PATH = Path(__file__).parent  #  Fijamos la ruta con respecto a este script

