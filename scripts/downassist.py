from scripts.config import MAIN_URL, REF_PATH

import requests
from pathlib import Path
import yarl


## Debemos realizar esto para mejor compatibilidad con jupyter notebooks
DATA_PATH = REF_PATH / ".." / "data" / "external" 

## Fuente de datos. 
DOWNLOAD_URL = MAIN_URL / "index.php"

def get_filename(link):
    head = requests.head(link)
    for u, v in head.headers.items():
        try:
            if v.index("filename"):
                name=v.split("filename=")[-1]
                name=name[1:-1]
                break
        except:
            pass
    return name

    
def parse_link(url, base=DOWNLOAD_URL):
    y_url= yarl.URL(url)
    link = base.with_query(y_url.query)
    return link


def download(link, filename, path=DATA_PATH, **kwargs):
    hint = kwargs.get("hint", 0)
    filelink = link / filename
    filepath = path / filename
    if hint:
        check = input(f"El archivo {filename} se guardara en {filepath}.\n¿Deseas continuar? Responda NO si quiere cancelar la descarga")
        if check == "NO":
            print("Revise el archivo a descargar\n y/o la ruta donde guardarlos en dgsiap.py")
    if not os.path.exists(filepath):
        try:
            odata = requests.get(link)
        except e:
            print(f"Error {e}. Status Code {odata.status_code}")
        print("La conexión procedio. Comenzamos con la descarga")
        with odata as data:
            with open(filepath, "wb") as f:
                f.write(data.content)
        print(f"Archivo {filename} descargado correctamente")
        print(f"Descargado el {date.today()}")
        print(f"Se encuentra en {str(filepath).split("..")[-1]}")
    else:
        print(f"El archivo ya fue descargado. Se encuentra en {str(filepath).split("..")[-1]}")