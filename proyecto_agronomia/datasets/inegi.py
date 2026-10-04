from pathlib import Path

import geopandas as gpd
import requests
from loguru import logger
from tqdm import tqdm

from proyecto_agronomia.config import (
    INEGI_ESTADOS_URL_TEMPLATE,
    INEGI_INTERIM_DIR,
    INEGI_MUNICIPIOS_URL_TEMPLATE,
)

def obtener_municipios_inegi(
    directorio: Path = INEGI_INTERIM_DIR,
) -> gpd.GeoDataFrame:
    """
    Descarga las geometrías municipales de México desde INEGI.

    Si el archivo local ya existe, se reutiliza para evitar
    descargar nuevamente la información.
    """

    directorio.mkdir(parents=True, exist_ok=True)

    ruta_geojson = directorio / "municipios_mexico_inegi.geojson"

    if ruta_geojson.exists():
        logger.info("Cargando municipios INEGI desde archivo local.")

        return gpd.read_file(ruta_geojson)

    features = []

    for id_estado in tqdm(
        range(1, 33),
        desc="Municipios INEGI",
    ):
        clave_estado = f"{id_estado:02d}"

        url = INEGI_MUNICIPIOS_URL_TEMPLATE.format(
            clave_estado=clave_estado
        )

        logger.info(
            f"Descargando municipios del estado {clave_estado}."
        )

        try:
            respuesta = requests.get(
                url,
                timeout=120,
            )

            respuesta.raise_for_status()
            datos = respuesta.json()

        except requests.RequestException as error:
            logger.error(
                f"Error descargando estado {clave_estado}: {error}"
            )
            raise

        features.extend(
            datos["features"]
        )

    municipios_geo = gpd.GeoDataFrame.from_features(
        features,
        crs="EPSG:4326",
    )

    municipios_geo.to_file(
        ruta_geojson,
        driver="GeoJSON",
    )

    logger.success(
        f"Municipios INEGI guardados: {len(municipios_geo):,}"
    )

    return municipios_geo

def obtener_estados_inegi(
    directorio: Path = INEGI_INTERIM_DIR,
) -> gpd.GeoDataFrame:
    """
    Descarga las geometrías de las 32 entidades federativas desde INEGI.

    Si el archivo local ya existe, se reutiliza para evitar
    descargar nuevamente la información.
    """

    directorio.mkdir(parents=True, exist_ok=True)

    ruta_geojson = directorio / "estados_mexico_inegi.geojson"

    if ruta_geojson.exists():
        logger.info("Cargando estados INEGI desde archivo local.")
        return gpd.read_file(ruta_geojson)

    features = []

    for id_estado in tqdm(
        range(1, 33),
        desc="Estados INEGI",
    ):
        clave_estado = f"{id_estado:02d}"

        url = INEGI_ESTADOS_URL_TEMPLATE.format(
            clave_estado=clave_estado
        )

        logger.info(
            f"Descargando estado {clave_estado}."
        )

        try:
            respuesta = requests.get(
                url,
                timeout=60,
            )
            respuesta.raise_for_status()
            datos = respuesta.json()

        except requests.RequestException as error:
            logger.error(
                f"Error descargando estado {clave_estado}: {error}"
            )
            raise

        features.extend(datos["features"])

    estados_geo = gpd.GeoDataFrame.from_features(
        features,
        crs="EPSG:4326",
    )

    estados_geo.to_file(
        ruta_geojson,
        driver="GeoJSON",
    )

    logger.success(
        f"Entidades geográficas guardadas: {len(estados_geo)}"
    )

    return estados_geo