from scripts.config import DATA_DIR
from datetime import date
import requests as r
import os

class WebFile:
    def __init__(self, link, source):
        self.link = link
        self.source = source

    def set_filename(self, force=0):
        if force!=0:
            self.filename = force
            return self.filename
        try:
            head = r.head(self.link)
            for v in head.headers.values():
                try:
                    if v.index("filename"):
                        name=v.split("filename=")[-1]
                        name=name[1:-1]
                        break
                except:
                    pass
            print(f"El nombre del archivo encontrado es {name}")
            self.filename = name
            return self.filename
        except:
            print("No fue posible obtener el nombre del archivo")
            self.filename = None
    def download(self):
        path = DATA_DIR / "pure" / self.source
        filepath = path / self.filename
        if not os.path.exists(filepath):
            try:
                response = r.get(self.link, stream=True)
            except:
                print(f"Error. Status Code {response.status_code}")
            
            with response as data:
                with open(filepath, "wb") as f:
                    f.write(data.content)
            self.downdate = date.today()
            print(f"Descarga completa. EL archivo se encuentra en /data/pure/{self.source}")
            self.ubication = filepath
        else:
            print(f"El archivo ya fue descargado. Se encuentra en /data/pure/{self.source}")


class File:
    def __init__(filename: str, path: Path):
        file_id = filename.split(".")
        self.name = file_id[0]
        self.ext = file_id[1]
        self.ubication = path / filename
    def get_encoding(self, force=False):
        """
            Intenta detectar el encoding de archivos.
                pars:
                    self: La ruta definida en el archivo
                    force: 0 por defecto. No detectar y
                            definir por usuario.
                    check: Despues de la detección consultará 
                            al usuario si esta deacuerdo.
                return: self.encoding. 
            Se le agrega al archivo el encoding encontrado.
            Consideraciones.
                * Recomendando usar si tu archivo es .txt o .csv.
                * Usar force si ya conoces el encoding y quieres 
                ahorrar tiempo en la detección.
                * La detección puede equivocarse, revisar encodings 
                tipicos del idioma del archivo.
        """
        if force:
            self.encode = force
        with open(filepath, 'rb') as file:
            data=file.read()
            res = cchardet.detect(data)

class FileTree:
    def __init__(self, source, root, branchs = []):
        self.root = root
        self.branch = branchs
    def download(self):
        path = DATA_DIR / "pure" / self.source
        filepath = path / self.filename
        if not os.path.exists(filepath):
            try:
                response = r.get(self.link, stream=True)
            except:
                print(f"Error. Status Code {response.status_code}")
            
            with response as data:
                with open(filepath, "wb") as f:
                    f.write(data.content)
            self.downdate = date.today()
            print(f"Descarga completa. EL archivo se encuentra en /data/pure/{self.source}")
            self.ubication = filepath
        else:
            print(f"El archivo ya fue descargado. Se encuentra en /data/pure/{self.source}")


class INEGITree(FileTree):
    def metadata(self, file):
        self.metadata = file
