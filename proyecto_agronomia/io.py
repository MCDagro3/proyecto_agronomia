"""Utilidades explícitas y reutilizables para archivos del proyecto."""

from email.message import Message
from pathlib import Path
import time

import cchardet
import pandas as pd
import requests


def nombre_archivo_remoto(
    url: str,
    timeout: int = 60,
    sesion: requests.Session | None = None,
) -> str:
    """Obtiene el nombre sugerido por HTTP o por la propia URL."""
    cliente = sesion or requests.Session()
    respuesta = cliente.head(url, allow_redirects=True, timeout=timeout)
    respuesta.raise_for_status()
    disposicion = respuesta.headers.get("Content-Disposition")
    if disposicion:
        mensaje = Message()
        mensaje["content-disposition"] = disposicion
        nombre = mensaje.get_filename()
        if nombre:
            return Path(nombre).name
    nombre_url = Path(respuesta.url.split("?", 1)[0]).name
    if not nombre_url:
        raise ValueError(f"No fue posible determinar el nombre de {url}")
    return nombre_url


def descargar_archivo(
    url: str,
    destino: Path,
    timeout: int = 120,
    intentos: int = 4,
    sesion: requests.Session | None = None,
) -> Path:
    """Descarga un archivo en flujo, de forma atómica y reanudable por archivo."""
    destino = Path(destino)
    if destino.exists():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".part")
    cliente = sesion or requests.Session()
    for intento in range(intentos):
        try:
            with cliente.get(url, stream=True, timeout=timeout) as respuesta:
                respuesta.raise_for_status()
                with temporal.open("wb") as archivo:
                    for bloque in respuesta.iter_content(chunk_size=1 << 20):
                        if bloque:
                            archivo.write(bloque)
            temporal.replace(destino)
            return destino
        except requests.RequestException:
            temporal.unlink(missing_ok=True)
            if intento == intentos - 1:
                raise
            time.sleep(2 * (intento + 1))
    raise RuntimeError(f"No se pudo descargar {url}")


def detectar_codificacion(ruta: Path, bytes_muestra: int = 1_000_000) -> str:
    """Estima la codificación leyendo solamente una muestra del archivo."""
    ruta = Path(ruta)
    with ruta.open("rb") as archivo:
        deteccion = cchardet.detect(archivo.read(bytes_muestra))
    codificacion = deteccion.get("encoding")
    if not codificacion:
        raise UnicodeError(f"No fue posible detectar la codificación de {ruta}")
    return codificacion


def leer_tabla(ruta: Path, **kwargs) -> pd.DataFrame:
    """Lee CSV o Excel y detecta la codificación del CSV si es necesario."""
    ruta = Path(ruta)
    sufijo = ruta.suffix.lower()
    if sufijo in {".xlsx", ".xls"}:
        return pd.read_excel(ruta, **kwargs)
    if sufijo not in {".csv", ".txt"}:
        raise ValueError(f"Formato tabular no soportado: {sufijo}")
    try:
        return pd.read_csv(ruta, **kwargs)
    except UnicodeDecodeError:
        parametros = {**kwargs, "encoding": detectar_codificacion(ruta)}
        return pd.read_csv(ruta, **parametros)


def normalizar_tabla(
    ruta_origen: Path,
    ruta_destino: Path,
    **kwargs,
) -> Path:
    """Lee una tabla y la guarda en una representación tabular reproducible."""
    datos = leer_tabla(ruta_origen, **kwargs)
    ruta_destino = Path(ruta_destino)
    ruta_destino.parent.mkdir(parents=True, exist_ok=True)
    if ruta_destino.suffix.lower() == ".csv":
        datos.to_csv(ruta_destino, index=False, encoding="utf-8")
    elif ruta_destino.suffix.lower() == ".xlsx":
        datos.to_excel(ruta_destino, index=False)
    elif ruta_destino.suffix.lower() == ".parquet":
        datos.to_parquet(ruta_destino, index=False)
    else:
        raise ValueError("El destino debe ser .csv, .xlsx o .parquet.")
    return ruta_destino
