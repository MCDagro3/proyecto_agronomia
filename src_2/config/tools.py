# Funciones utilizadas en todo el proyecto
from bs4 import Tag
import requests


def require_tag(tag: Tag | None, description: str) -> Tag:
    if tag is None:
        raise RuntimeError(f"No se encontro {description} en DGSIAP")
    return tag


def download_file(url, savepath):
    response = requests.head(url)
    filename = response.headers['Content-Disposition'].split("=")[1][1:-1]
    if not (savepath / filename).exists():
        response = requests.get(url)
        with open(savepath / filename, "wb") as file:
            file.write(response.content)
    return str(savepath / filename)