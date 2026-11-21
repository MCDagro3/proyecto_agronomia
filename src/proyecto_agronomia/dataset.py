"""Comandos de adquisición de datos del proyecto agronómico."""

from loguru import logger
import typer

from proyecto_agronomia.config import ANIOS
from datasets.agricultura import (
    descargar_datos_agricolas,
    descargar_diccionario_agricola,
    descargar_reporte_agroprograma,
    descargar_reporte_avance,
)
from datasets.edafologia import (
    descargar_diccionario_edafologia,
    descargar_edafologia_inegi,
)
from datasets.inegi import (
    SERIES_USO_SUELO,
    descargar_series_uso_suelo,
    obtener_estados_inegi,
    obtener_municipios_inegi,
)
from datasets.mapbiomas import procesar_directorio_mapbiomas


app = typer.Typer(help="Adquisición de datos del proyecto de agronomía.")


@app.command()
def agricultura():
    """Descarga los datos agrícolas y su diccionario."""
    logger.info(f"Descargando datos agrícolas para {ANIOS[0]}-{ANIOS[-1]}.")
    archivos = descargar_datos_agricolas(ANIOS)
    descargar_diccionario_agricola()
    logger.success(f"Agricultura terminada. {len(archivos)} archivos disponibles.")


@app.command()
def inegi():
    """Descarga las geometrías municipales y estatales de INEGI."""
    municipios = obtener_municipios_inegi()
    estados = obtener_estados_inegi()
    logger.success(
        f"INEGI terminado. {len(municipios):,} municipios y "
        f"{len(estados)} estados disponibles."
    )


@app.command("dgsiap-avance")
def dgsiap_avance(
    anio: int = typer.Option(0, help="Año; 0 consulta el último corte."),
    mes: int = typer.Option(0, help="Mes; 0 usa el último corte."),
):
    """Descarga un reporte nacional del avance agrícola de DGSIAP."""
    ruta = descargar_reporte_avance(anio=anio, mes=mes)
    logger.success(f"Avance agrícola guardado en {ruta}")


@app.command("dgsiap-agroprograma")
def dgsiap_agroprograma(
    anio: int = typer.Option(0, help="Año; 0 consulta el vigente."),
):
    """Descarga la intención nacional de siembra y cosecha de DGSIAP."""
    ruta = descargar_reporte_agroprograma(anio=anio)
    logger.success(f"AgroPrograma guardado en {ruta}")


@app.command("inegi-uso-suelo")
def inegi_uso_suelo(
    series: str = typer.Option(
        "VII",
        help="Serie romana, lista separada por comas o 'all'.",
    ),
    extraer: bool = typer.Option(False, help="Extraer los ZIP descargados."),
):
    """Descarga series nacionales de uso del suelo y vegetación de INEGI."""
    seleccion = (
        SERIES_USO_SUELO
        if series.lower() == "all"
        else tuple(valor.strip().upper() for valor in series.split(","))
    )
    rutas = descargar_series_uso_suelo(seleccion, extraer=extraer)
    logger.success(f"Series de uso del suelo disponibles: {len(rutas)}")


@app.command("mapbiomas-procesar")
def mapbiomas_procesar():
    """Extrae las clases agrícolas de los TIFF disponibles de MapBiomas."""
    rutas = procesar_directorio_mapbiomas()
    logger.success(f"Rasters MapBiomas procesados: {len(rutas)}")


@app.command()
def edafologia():
    """Descarga la información edafológica y su diccionario."""
    descargar_edafologia_inegi()
    descargar_diccionario_edafologia()
    logger.success("Descarga edafológica terminada.")


if __name__ == "__main__":
    app()
