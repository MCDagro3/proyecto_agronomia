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


class FileTree:
    def __init__(root, branchs = []):
        self.root = root
        self.branch = branchs