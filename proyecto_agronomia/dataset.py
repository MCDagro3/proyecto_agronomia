import typer
from loguru import logger

from proyecto_agronomia.config import ANIOS

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


if __name__ == "__main__":
    app()