
from scripts.config import DATA_FOLDERS
import os

class File:
    def __init__(self, path, filename: str, source):
        self.link = path
        self.source = source
        self.file = filename
        name_ext = filename.split(".")
        self.name = name_ext[0]
        self.ext = name_ext[1]
        self.state = 0
        self.filepath = ""
    def get_local_ubication(self, **kwargs):
        ext = kwargs.get("ext", 1)
        if self.state == 0:
            value = self.file if ext else self.name
            local_ubication = self.link / value
            self.ubication = self.link / value
            return local_ubication
        else:
            return self.ubication
    def downcheck(self, folder="raw"):
        if not os.path.exists(self.filepath):
            self.state = 0 
        if self.state:
            print("El archivo ya existe")
            print(f"Se encuentra en {self.filepath}")
        else:
            from scripts.download import download
            filepath = DATA_FOLDERS[folder] / self.source
            download(self.link, self.file, filepath)
            self.state = 1
            self.filepath = filepath
            self.ubication = filepath / self.file
