from pathlib import Path

import requests
import typer
from loguru import logger
from tqdm import tqdm
import geopandas as gpd
import pandas as pd

from proyecto_agronomia.datasets.agricultura import (
    descargar_datos_agricolas,
    descargar_diccionario_agricola,
)

from proyecto_agronomia.datasets.clima import (
    descargar_clima_batch,
    descargar_clima_estado,
    descargar_clima_estados,
    descargar_clima_todos_estados,
    obtener_clima_lote,
)

from proyecto_agronomia.datasets.edafologia import (
    descargar_diccionario_edafologia,
    descargar_edafologia_inegi,
)

from proyecto_agronomia.datasets.inegi import (
    obtener_estados_inegi,
    obtener_municipios_inegi,
)
from proyecto_agronomia.config import (
    ANIOS,
)

app = typer.Typer()




@app.command()
def main():
    """Descarga los datos agrícolas correspondientes al periodo de estudio."""

    logger.info(
        f"Descargando datos agrícolas para {ANIOS[0]}-{ANIOS[-1]}."
    )

    archivos = descargar_datos_agricolas(ANIOS)

    logger.success(
        f"Proceso terminado. {len(archivos)} archivos disponibles."
    )


if __name__ == "__main__":
    app()