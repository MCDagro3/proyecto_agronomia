from pathlib import Path
import zipfile

import requests
from loguru import logger

from proyecto_agronomia.config import (
    EDAFOLOGIA_DICCIONARIO_PATH,
    EDAFOLOGIA_DICCIONARIO_URL,
    EDAFOLOGIA_RAW_DIR,
    EDAFOLOGIA_URL,
)

from proyecto_agronomia.config import (
    EDAFOLOGIA_RAW_DIR,
    EDAFOLOGIA_URL,
    EDAFOLOGIA_DICCIONARIO_PATH,
    EDAFOLOGIA_DICCIONARIO_URL,
)

def descargar_edafologia_inegi(
    directorio: Path = EDAFOLOGIA_RAW_DIR,
) -> Path:
    """
    Descarga y extrae el Conjunto Nacional de Información Edafológica
    escala 1:250 000 Serie III de INEGI.

    El archivo original se descarga como ZIP y se conserva dentro de
    data/raw/edafologia. Si ya fue descargado y extraído, se reutiliza.

    Parameters
    ----------
    directorio : Path
        Directorio donde se almacenarán los datos edafológicos.

    Returns
    -------
    Path
        Directorio que contiene los archivos extraídos.
    """

    directorio.mkdir(
        parents=True,
        exist_ok=True,
    )

    ruta_zip = (
        directorio
        / "edafologia_serie_iii_inegi.zip"
    )

    directorio_extraido = (
        directorio
        / "serie_iii"
    )

    if not ruta_zip.exists():
        logger.info(
            "Descargando información edafológica de INEGI..."
        )

        try:
            respuesta = requests.get(
                EDAFOLOGIA_URL,
                timeout=300,
                stream=True,
            )

            respuesta.raise_for_status()

            with ruta_zip.open("wb") as archivo:
                for bloque in respuesta.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if bloque:
                        archivo.write(bloque)

        except requests.RequestException as error:
            logger.error(
                f"Error descargando edafología: {error}"
            )
            raise

        logger.success(
            "Archivo edafológico descargado "
            f"({ruta_zip.stat().st_size / (1024**2):.2f} MB)"
        )

    else:
        logger.info(
            "El archivo edafológico ya existe."
        )

    if directorio_extraido.exists():
        logger.info(
            "Los datos edafológicos ya fueron extraídos."
        )
        return directorio_extraido

    logger.info(
        "Extrayendo información edafológica..."
    )

    directorio_extraido.mkdir(
        parents=True,
        exist_ok=True,
    )

    with zipfile.ZipFile(
        ruta_zip,
        "r",
    ) as archivo_zip:
        archivo_zip.extractall(
            directorio_extraido
        )

    logger.success(
        "Información edafológica extraída."
    )

    return directorio_extraido

def descargar_diccionario_edafologia(
    ruta: Path = EDAFOLOGIA_DICCIONARIO_PATH,
) -> Path:
    """
    Descarga el Diccionario de Datos Edafológicos
    escala 1:250 000, versión 4, publicado por INEGI.

    El documento se conserva sin modificaciones dentro de
    references/edafologia/. Si ya existe localmente, se reutiliza.

    Parameters
    ----------
    ruta : Path
        Ruta donde se almacenará el diccionario PDF.

    Returns
    -------
    Path
        Ruta local del diccionario edafológico.
    """

    ruta.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if ruta.exists():
        logger.info(
            "El diccionario edafológico ya existe."
        )
        return ruta

    logger.info(
        "Descargando diccionario edafológico de INEGI..."
    )

    try:
        respuesta = requests.get(
            EDAFOLOGIA_DICCIONARIO_URL,
            timeout=120,
        )

        respuesta.raise_for_status()

        ruta.write_bytes(
            respuesta.content
        )

    except requests.RequestException as error:
        logger.error(
            "Error descargando el diccionario "
            f"edafológico: {error}"
        )
        raise

    logger.success(
        "Diccionario edafológico descargado: "
        f"{ruta.name}"
    )

    return ruta
