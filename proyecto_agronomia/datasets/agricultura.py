from pathlib import Path

import requests
from loguru import logger
from tqdm import tqdm

from proyecto_agronomia.config import (
    AGRICULTURA_DICCIONARIO_PATH,
    AGRICULTURA_DICCIONARIO_URL,
    AGRICULTURA_RAW_DIR,
    AGRICULTURA_URL_TEMPLATE,
)


def descargar_datos_agricolas(
    anios: list[int],
    directorio: Path = AGRICULTURA_RAW_DIR,
) -> list[Path]:
    """
    Descarga los archivos agrícolas anuales de la Secretaría de Agricultura.

    Los archivos se guardan en data/raw/agricultura. Si un archivo ya existe,
    no se vuelve a descargar.

    Parameters
    ----------
    anios : list[int]
        Años que se desean descargar.
    directorio : Path
        Directorio donde se almacenarán los archivos CSV.

    Returns
    -------
    list[Path]
        Rutas de los archivos disponibles después de la descarga.
    """

    directorio.mkdir(parents=True, exist_ok=True)

    archivos = []

    for anio in tqdm(anios, desc="Datos agrícolas"):
        url = AGRICULTURA_URL_TEMPLATE.format(anio=anio)
        ruta = directorio / f"agricola_{anio}.csv"

        if ruta.exists():
            logger.info(f"[{anio}] El archivo ya existe.")
            archivos.append(ruta)
            continue

        logger.info(f"[{anio}] Descargando...")

        try:
            respuesta = requests.get(
                url,
                timeout=120,
            )
            respuesta.raise_for_status()

            ruta.write_bytes(
                respuesta.content
            )

        except requests.RequestException as error:
            logger.error(
                f"[{anio}] Error durante la descarga: {error}"
            )
            continue

        logger.success(
            f"[{anio}] Descargado "
            f"({ruta.stat().st_size / (1024**2):.2f} MB)"
        )

        archivos.append(ruta)

    return archivos


def descargar_diccionario_agricola(
    ruta: Path = AGRICULTURA_DICCIONARIO_PATH,
) -> Path:
    """
    Descarga el diccionario oficial de los datos de Cierre de la
    Producción Agrícola de la DGSIAP.

    El archivo se almacena en references/ como documentación de la
    fuente de datos. Si el archivo ya existe, no se vuelve a descargar.

    Parameters
    ----------
    ruta : Path
        Ruta donde se almacenará el diccionario XLSX.

    Returns
    -------
    Path
        Ruta del diccionario disponible localmente.
    """

    ruta.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if ruta.exists():
        logger.info(
            "El diccionario agrícola ya existe."
        )
        return ruta

    logger.info(
        "Descargando diccionario agrícola DGSIAP..."
    )

    try:
        respuesta = requests.get(
            AGRICULTURA_DICCIONARIO_URL,
            timeout=120,
        )

        respuesta.raise_for_status()

        ruta.write_bytes(
            respuesta.content
        )

    except requests.RequestException as error:
        logger.error(
            "Error descargando el diccionario "
            f"agrícola: {error}"
        )
        raise

    logger.success(
        "Diccionario agrícola descargado: "
        f"{ruta.name}"
    )

    return ruta