"""
    Extraccion de datos desde DGSIAP.
"""

# Importamos librerias requeridas
import requests
from bs4 import BeautifulSoup
import yarl
from pathlib import Path

# Definimos la ruta de descarga de archivos.

DATA_PATH = Path("data") / "external"

# Definimos las urls a utilizar
## URL BASE: De esta parten las siguientes
MAIN_URL = yarl.URL("https://nube.agricultura.gob.mx")
## Pagina principal: De aqui obtendremos la información
PAGE_URL = MAIN_URL / "datosAbiertos/"
## Fuente de datos.
DOWNLOAD_URL = MAIN_URL / "index.php"

## Menu para elegir entre los datos agricolas y los datos pecuarios.
print("Bienvenido al script de descarga de datos abiertos del DGSIAP.")

info = {
    "Agricola": "Agricola.php",
    "Pecuaria": "Pecuario.php",
}

value = input(f"Ingrese la categoria de los datos a consultar.\n{" \n".join(info.keys())}: ")

try:
    BOT_URL = PAGE_URL / info[value]
except KeyError:
    print("Categoria no valida. Por favor, ingrese una categoria valida.")
    exit(1)

# Intento de conexión
response = requests.get(BOT_URL)
if response.status_code != 200:
    print(f"Error al acceder a la pagina: {response.status_code}")
    exit(1)

# Mandamos la información para su recopilación
page = BeautifulSoup(response.content, "lxml")
print("Conexion Establecida")

