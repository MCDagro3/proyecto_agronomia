"""Seleccion y preparacion de cultivos principales para modelos v1."""

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from proyecto_agronomia.config import PROCESSED_DATA_DIR

RUTA_INTEGRADA = PROCESSED_DATA_DIR / "agricultura_clima_edafologia_historial_2003_2025.csv"

VARIABLES_HISTORICAS = [
    "rendimiento_hist_anios",
    "rendimiento_anio_anterior",
    "rendimiento_hist_media",
    "rendimiento_hist_desviacion",
    "rendimiento_hist_cv",
]

VARIABLES_NUMERICAS = [
    "Anio",
    "temperatura_media_ciclo_c",
    "precipitacion_ciclo_mm",
    "dias_clima_ciclo",
    "grupo_suelo_dominante_pct",
    "grupos_suelo_n",
    *VARIABLES_HISTORICAS,
]
VARIABLES_CATEGORICAS = [
    "Nomestado",
    "Nomcicloproductivo",
    "Nommodalidad",
    "grupo_suelo_dominante",
    "textura_dominante",
]
COLUMNAS_BASE = [
    "cvegeo",
    "Anio",
    "Nomestado",
    "Nommunicipio",
    "Nomcultivo",
    "Nomcicloproductivo",
    "Nommodalidad",
    "Nomunidad",
    "Cosechada",
    "Volumenproduccion",
    *VARIABLES_NUMERICAS[1:],
    *VARIABLES_CATEGORICAS[3:],
]


def catalogar_cultivos(
    ruta: Path = RUTA_INTEGRADA,
    unidad: str = "Tonelada",
    tamano_bloque: int = 150_000,
) -> pd.DataFrame:
    """Resume cobertura y superficie sin cargar el archivo completo."""
    acumulados = []
    anios = defaultdict(set)
    municipios = defaultdict(set)
    columnas = ["Nomcultivo", "Nomunidad", "Cosechada", "Anio", "cvegeo"]
    for bloque in pd.read_csv(
        Path(ruta),
        usecols=columnas,
        dtype={"cvegeo": "string"},
        chunksize=tamano_bloque,
        low_memory=False,
    ):
        bloque = bloque.loc[bloque["Nomunidad"].eq(unidad)].copy()
        bloque["Cosechada"] = pd.to_numeric(bloque["Cosechada"], errors="coerce")
        acumulados.append(
            bloque.groupby("Nomcultivo", observed=True)["Cosechada"].agg(
                superficie_cosechada="sum", registros="count"
            )
        )
        for cultivo, grupo in bloque.groupby("Nomcultivo", observed=True):
            anios[cultivo].update(grupo["Anio"].dropna().astype(int).unique())
            municipios[cultivo].update(grupo["cvegeo"].dropna().unique())
    catalogo = pd.concat(acumulados).groupby(level=0).sum().reset_index()
    catalogo["anios"] = catalogo["Nomcultivo"].map(lambda x: len(anios[x]))
    catalogo["municipios"] = catalogo["Nomcultivo"].map(lambda x: len(municipios[x]))
    return catalogo.sort_values("superficie_cosechada", ascending=False).reset_index(drop=True)


def seleccionar_principales(
    catalogo: pd.DataFrame,
    cantidad: int = 10,
    minimo_anios: int = 15,
    minimo_municipios: int = 100,
) -> pd.DataFrame:
    """Elige por superficie entre cultivos con cobertura suficiente."""
    elegibles = catalogo.loc[
        catalogo["anios"].ge(minimo_anios) & catalogo["municipios"].ge(minimo_municipios)
    ]
    return elegibles.head(cantidad).reset_index(drop=True)


def cargar_registros_cultivos(
    cultivos: list[str],
    ruta: Path = RUTA_INTEGRADA,
    unidad: str = "Tonelada",
    tamano_bloque: int = 150_000,
) -> pd.DataFrame:
    """Carga en una sola pasada solo los cultivos que seran entrenados."""
    seleccionados = set(cultivos)
    bloques = []
    for bloque in pd.read_csv(
        Path(ruta),
        usecols=COLUMNAS_BASE,
        dtype={"cvegeo": "string"},
        chunksize=tamano_bloque,
        low_memory=False,
    ):
        mascara = bloque["Nomcultivo"].isin(seleccionados) & bloque["Nomunidad"].eq(unidad)
        if mascara.any():
            bloques.append(bloque.loc[mascara].copy())
    if not bloques:
        raise ValueError("No se encontraron registros de los cultivos seleccionados.")
    return pd.concat(bloques, ignore_index=True)


def preparar_cultivo(datos_nacionales: pd.DataFrame, cultivo: str) -> pd.DataFrame:
    """Consolida una observacion modelable por municipio, ciclo y modalidad."""
    datos = datos_nacionales.loc[datos_nacionales["Nomcultivo"].eq(cultivo)].copy()
    numericas = ["Cosechada", "Volumenproduccion", *VARIABLES_NUMERICAS]
    datos[numericas] = datos[numericas].apply(pd.to_numeric, errors="coerce")
    claves = [
        "cvegeo",
        "Anio",
        "Nomcultivo",
        "Nomcicloproductivo",
        "Nommodalidad",
        "Nomunidad",
    ]
    datos = datos.groupby(claves, as_index=False, observed=True, dropna=False).agg(
        Nomestado=("Nomestado", "first"),
        Nommunicipio=("Nommunicipio", "first"),
        Cosechada=("Cosechada", "sum"),
        Volumenproduccion=("Volumenproduccion", "sum"),
        temperatura_media_ciclo_c=("temperatura_media_ciclo_c", "first"),
        precipitacion_ciclo_mm=("precipitacion_ciclo_mm", "first"),
        dias_clima_ciclo=("dias_clima_ciclo", "first"),
        grupo_suelo_dominante=("grupo_suelo_dominante", "first"),
        grupo_suelo_dominante_pct=("grupo_suelo_dominante_pct", "first"),
        grupos_suelo_n=("grupos_suelo_n", "first"),
        textura_dominante=("textura_dominante", "first"),
        rendimiento_hist_anios=("rendimiento_hist_anios", "first"),
        rendimiento_anio_anterior=("rendimiento_anio_anterior", "first"),
        rendimiento_hist_media=("rendimiento_hist_media", "first"),
        rendimiento_hist_desviacion=("rendimiento_hist_desviacion", "first"),
        rendimiento_hist_cv=("rendimiento_hist_cv", "first"),
    )
    datos["Rendimiento"] = datos["Volumenproduccion"] / datos["Cosechada"]
    datos = datos.replace([np.inf, -np.inf], np.nan)
    datos = datos.loc[
        datos["Cosechada"].gt(0) & datos["Rendimiento"].gt(0) & datos["Rendimiento"].notna()
    ].copy()
    for columna in VARIABLES_CATEGORICAS:
        datos[columna] = datos[columna].astype("string").fillna("Sin informacion")
    # El historial usa exclusivamente anos anteriores y por construccion es nulo
    # al inicio de cada serie. Se conserva: el pipeline lo imputa dentro de cada
    # particion, sin descartar justamente los primeros anos del cultivo.
    numericas_obligatorias = [
        columna for columna in VARIABLES_NUMERICAS if columna not in VARIABLES_HISTORICAS
    ]
    return datos.dropna(subset=numericas_obligatorias).reset_index(drop=True)


def separar_xy(datos: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    variables = [*VARIABLES_NUMERICAS, *VARIABLES_CATEGORICAS]
    return datos[variables].copy(), datos["Rendimiento"].copy()
