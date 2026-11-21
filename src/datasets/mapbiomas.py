"""Procesamiento explícito de coberturas agrícolas de MapBiomas."""

from pathlib import Path

from loguru import logger
import numpy as np
import pandas as pd

from proyecto_agronomia.config import (
    MAPBIOMAS_PROCESSED_DIR,
    MAPBIOMAS_RAW_DIR,
)

CLASES_AGRICOLAS_MAPBIOMAS = {
    19: "Cultivo anual",
    36: "Cultivo perenne",
    21: "Mosaico agropecuario",
}


def extraer_pixeles_agricolas_mapbiomas(
    ruta_raster: Path,
    ruta_salida: Path | None = None,
    clases: dict[int, str] = CLASES_AGRICOLAS_MAPBIOMAS,
) -> pd.DataFrame:
    """Extrae coordenadas y clase de los píxeles agrícolas de un raster.

    Esta representación puede ser muy grande. Para análisis nacionales se
    recomienda usar posteriormente estadística zonal por municipio.
    """
    try:
        import rasterio
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(
            "MapBiomas requiere rasterio. Instala las dependencias del proyecto."
        ) from error

    ruta_raster = Path(ruta_raster)
    if not ruta_raster.is_file():
        raise FileNotFoundError(f"No existe el raster: {ruta_raster}")

    with rasterio.open(ruta_raster) as raster:
        matriz = raster.read(1)
        mascara = np.isin(matriz, list(clases))
        filas, columnas = np.nonzero(mascara)
        coordenadas_x, coordenadas_y = rasterio.transform.xy(raster.transform, filas, columnas)
        resultado = pd.DataFrame(
            {
                "x": coordenadas_x,
                "y": coordenadas_y,
                "clase_id": matriz[filas, columnas],
            }
        )
        resultado["clase"] = resultado["clase_id"].map(clases)
        resultado.attrs["crs"] = str(raster.crs)
        resultado.attrs["raster_origen"] = str(ruta_raster)

    if ruta_salida is not None:
        ruta_salida = Path(ruta_salida)
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        sufijos = "".join(ruta_salida.suffixes).lower()
        if sufijos.endswith((".csv", ".csv.gz")):
            resultado.to_csv(ruta_salida, index=False)
        elif sufijos.endswith(".parquet"):
            resultado.to_parquet(ruta_salida, index=False)
        else:
            raise ValueError("La salida debe ser .csv, .csv.gz o .parquet.")
        logger.success(f"Cobertura MapBiomas guardada en {ruta_salida}")
    return resultado


def procesar_directorio_mapbiomas(
    directorio_entrada: Path = MAPBIOMAS_RAW_DIR,
    directorio_salida: Path = MAPBIOMAS_PROCESSED_DIR,
) -> list[Path]:
    """Procesa todos los TIFF del directorio y evita repetir salidas."""
    directorio_entrada = Path(directorio_entrada)
    if not directorio_entrada.is_dir():
        raise FileNotFoundError(f"No existe el directorio: {directorio_entrada}")
    directorio_salida.mkdir(parents=True, exist_ok=True)
    salidas: list[Path] = []
    for raster in sorted([*directorio_entrada.glob("*.tif"), *directorio_entrada.glob("*.tiff")]):
        anio = raster.stem.split("_")[0]
        salida = directorio_salida / f"agricultura_mapbiomas_{anio}.csv.gz"
        if salida.exists():
            logger.info(f"MapBiomas {anio}: salida existente.")
        else:
            extraer_pixeles_agricolas_mapbiomas(raster, salida)
        salidas.append(salida)
    return salidas
