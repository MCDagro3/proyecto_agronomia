from scripts.config import DATA_DIR
from datetime import date
import requests as r
import os
import cchardet
import pandas as pd


class File:
    def __init__(self, path, source):
        self.ubication = path
        self.source = source
        self.filename = str(path).split("/")[-1]

 
    def open(self, **kwargs):
        parms = kwargs.get("pars", [False,0])        
        ext = self.filename.split(".")[-1]
        assert ext in ("csv", "xlsx")
        if ext == "csv":
            file = pd.read_csv(self.ubication, **parms[1]) if parms[0] else pd.read_csv(self.ubication)
        elif ext=="xlsx":
            file = pd.read_excel(self.ubication, **parms[1]) if parms[0] else pd.read_excel(self.ubication)
        return file



class FileTree:
    def __init__(self, root: File, branch: list, source: str):
        self.root = root
        self.branch = branch
        self.source = source





class WebFile:
    def __init__(self, link, source: str):
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
        else:
            print(f"El archivo ya fue descargado. Se encuentra en /data/pure/{self.source}")
        self.ubication = filepath
    def get_extension(self):
        assert self.filename is not None, "No hay nombre de archivo"
        self.ext = self.filename.split(".")[-1]

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
        if force != False:
            self.encode = force
        else:
            try:
                self.encode = self.dect_encode['encoding']
                print(f"El archivo fue procesado. Encode de la útlima vez {self.encode}")
            except:
                with open(self.ubication, 'rb') as file:
                    data=file.read()
                    res = cchardet.detect(data)
                self.dect_encode = res
                self.encode = res['encoding']
    def load(self):
        try:
            print(f"El archivo ya esta cargado {self.loader}")
        except:
            self.get_extension()
            assert self.ext in ("csv","xlsx"), "La función solo admite .csv y .xlsx"
            loader = pd.read_csv if self.ext == "csv" else pd.read_excel
            try:
                loader(self.ubication)
            except UnicodeDecodeError as e:
                self.get_encoding()
                if self.ext == "csv":
                    loader = lambda x: pd.read_csv(x, encoding=self.encode, low_memory=False)
                else:
                    print("Revisa el archivo", self.filename)
            self.loader = loader
        
    def open(self):
        try:
            return self.loader(self.ubication)
        except:
            self.load()
            return self.loader(self.ubication)
    
        
    def prepare(self, **kwargs):
        name = kwargs.get("name", self.filename.split(".")[0])
        ideal_encode = "utf-8"
        assert self.ext in ("csv", "xlsx"), "Solo funciona para .csv y .xlsx"
        assert self.loader, "Carga el archivo"
        file = self.open()
        path = DATA_DIR / "raw" / self.source

        filepath = path / f"{name}.{self.ext}"
        file.to_csv(filepath, encoding=ideal_encode) if self.ext == "csv" else file.to_excel(filepath)
        preparefile = File(filepath, self.source)
        return preparefile


class WebTree:
    def __init__(self, source: str, root, branchs: list):
        self.root = root
        self.branch = branchs
        self.source = source
    def download(self):
        n = 1
        path = DATA_DIR / "pure" / self.source
        root_file = WebFile(self.root, self.source)
        root_file.set_filename()
        root_file.download()
        self.rootfile = root_file
        print(f"Archivo Descargado {n}/{1 + len(self.branch)}")
        self.branchfiles = []
        for file in self.branch:
            bfile = WebFile(file, self.source)
            bfile.set_filename()
            bfile.download()
            n += 1
            self.branchfiles.append(bfile)
            print(f"Archivo Descargado {n}/{1 + len(self.branch)}")

    def load(self):
        self.rootfile.load()
        for file in self.branchfiles:
            file.load()
        print("Los archivos estan cargados")

class INEGITree(WebTree):
    def metadata(self, file):
        self.metadata = file
