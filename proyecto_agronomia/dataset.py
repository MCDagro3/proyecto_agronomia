import typer
from loguru import logger
import pandas as pd
from pathlib import Path

from proyecto_agronomia.config import (ANIOS, CONAGUA_PROCESSED_DIR) 

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

from proyecto_agronomia.datasets.clima_con import (
    descargar_catalogo_conagua,
    descargar_estaciones_conagua,
)

app = typer.Typer(
    help="Adquisición de datos del proyecto de agronomía."
)


@app.command()
def agricultura():
    """Descarga los datos agrícolas y su diccionario."""

    logger.info(
        f"Descargando datos agrícolas para {ANIOS[0]}-{ANIOS[-1]}."
    )

    archivos = descargar_datos_agricolas(ANIOS)
    descargar_diccionario_agricola()

    logger.success(
        f"Agricultura terminada. "
        f"{len(archivos)} archivos disponibles."
    )


@app.command()
def inegi():
    """Descarga las geometrías municipales y estatales de INEGI."""

    municipios = obtener_municipios_inegi()
    estados = obtener_estados_inegi()

    logger.success(
        f"INEGI terminado. "
        f"{len(municipios):,} municipios y "
        f"{len(estados)} estados disponibles."
    )


@app.command()
def edafologia():
    """Descarga la información edafológica y su diccionario."""

    descargar_edafologia_inegi()
    descargar_diccionario_edafologia()

    logger.success(
        "Descarga edafológica terminada."
    )

@app.command("conagua-catalogo")
def conagua_catalogo():
    """
    Descarga el catálogo nacional KMZ de estaciones
    climatológicas del Servicio Meteorológico Nacional.
    """

    logger.info(
        "Iniciando descarga del catálogo CONAGUA."
    )

    ruta = descargar_catalogo_conagua()

    logger.success(
        f"Catálogo CONAGUA disponible en: {ruta}"
    )


@app.command("conagua-estaciones")
def conagua_estaciones(
    catalogo: Path = typer.Option(
        CONAGUA_PROCESSED_DIR
        / "estaciones_seleccionadas_continentales_1981_2022.csv",
        "--catalogo",
        help="CSV con estaciones seleccionadas y URLs mensuales.",
    ),
    pausa: float = typer.Option(
        1.0,
        "--pausa",
        min=0.0,
        help="Segundos de espera entre descargas.",
    ),
):
    """
    Descarga los TXT mensuales de las estaciones
    seleccionadas de CONAGUA.
    """

    if not catalogo.is_file():
        logger.error(
            f"No existe el catálogo de estaciones: {catalogo}"
        )
        raise typer.Exit(code=1)

    estaciones = pd.read_csv(
        catalogo,
        dtype={"estacion": str},
    )

    logger.info(
        f"Descargando {len(estaciones)} estaciones CONAGUA."
    )

    archivos = descargar_estaciones_conagua(
        estaciones=estaciones,
        pausa=pausa,
    )

    logger.success(
        f"CONAGUA terminado. "
        f"{len(archivos)} archivos TXT disponibles."
    )
if __name__ == "__main__":
    app()