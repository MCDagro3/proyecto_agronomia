"""Selección y preparación de cultivos con el dataset depurado para modelado."""

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from proyecto_agronomia.config import PROCESSED_DATA_DIR

RUTA_MODELADO = PROCESSED_DATA_DIR / "agricultura_modelado_2003_2025.csv"
# Alias temporal para no romper llamadas externas que importaban este nombre.
RUTA_INTEGRADA = RUTA_MODELADO
OBJETIVO = "Rendimiento_modelado"

VARIABLES_HISTORICAS = [
    "rendimiento_hist_anios",
    "rendimiento_anio_anterior",
    "rendimiento_hist_media",
    "rendimiento_hist_desviacion",
    "rendimiento_hist_cv",
]

VARIABLES_NUMERICAS = [
    "Anio", "temperatura_media_ciclo_c", "precipitacion_ciclo_mm",
    "dias_clima_ciclo", "grupo_suelo_dominante_pct", "grupos_suelo_n",
    *VARIABLES_HISTORICAS,
]
VARIABLES_CATEGORICAS = [
    "Nomestado", "Nomcicloproductivo", "Nommodalidad",
    "grupo_suelo_dominante", "textura_dominante",
]
COLUMNAS_BASE = [
    "cvegeo", "Anio", "Idcultivo", "Idciclo", "Idmodalidad",
    "Idunidadmedida", "Nomestado_canonico", "Nommunicipio_canonico",
    "Nomcultivo_canonico", "Nomcicloproductivo", "Nommodalidad",
    "Nomunidad", "Cosechada", "Volumenproduccion", OBJETIVO,
    "registro_apto_modelado", *VARIABLES_NUMERICAS[1:],
    *VARIABLES_CATEGORICAS[3:],
]


def catalogar_cultivos(
    ruta: Path = RUTA_MODELADO,
    unidad: str = "Tonelada",
    tamano_bloque: int = 150_000,
) -> pd.DataFrame:
    """Resume cobertura y superficie sin cargar el archivo completo."""
    acumulados = []
    anios = defaultdict(set)
    municipios = defaultdict(set)
    columnas = [
        "Idcultivo", "Nomcultivo_canonico", "Nomunidad", "Cosechada",
        "Anio", "cvegeo", "registro_apto_modelado",
    ]
    for bloque in pd.read_csv(
        Path(ruta), usecols=columnas, dtype={"cvegeo": "string"},
        chunksize=tamano_bloque, low_memory=False,
    ):
        bloque = bloque.loc[
            bloque["Nomunidad"].eq(unidad)
            & bloque["registro_apto_modelado"].eq(True)  # noqa: E712
        ].copy()
        if bloque.empty:
            continue
        bloque["Cosechada"] = pd.to_numeric(bloque["Cosechada"], errors="coerce")
        acumulados.append(
            bloque.groupby(
                ["Idcultivo", "Nomcultivo_canonico"], observed=True
            )["Cosechada"]
            .agg(superficie_cosechada="sum", registros="count")
        )
        for cultivo, grupo in bloque.groupby("Idcultivo", observed=True):
            cultivo = int(cultivo)
            anios[cultivo].update(grupo["Anio"].dropna().astype(int).unique())
            municipios[cultivo].update(grupo["cvegeo"].dropna().unique())
    if not acumulados:
        raise ValueError("No se encontraron registros aptos para catalogar cultivos.")
    catalogo = (
        pd.concat(acumulados)
        .groupby(level=[0, 1])
        .sum()
        .reset_index()
        .rename(columns={"Nomcultivo_canonico": "Nomcultivo"})
    )
    catalogo["anios"] = catalogo["Idcultivo"].map(lambda x: len(anios[int(x)]))
    catalogo["municipios"] = catalogo["Idcultivo"].map(
        lambda x: len(municipios[int(x)])
    )
    return catalogo.sort_values("superficie_cosechada", ascending=False).reset_index(drop=True)


def seleccionar_principales(
    catalogo: pd.DataFrame,
    cantidad: int = 10,
    minimo_anios: int = 15,
    minimo_municipios: int = 100,
) -> pd.DataFrame:
    """Elige por superficie entre cultivos con cobertura suficiente."""
    elegibles = catalogo.loc[
        catalogo["anios"].ge(minimo_anios)
        & catalogo["municipios"].ge(minimo_municipios)
    ]
    return elegibles.head(cantidad).reset_index(drop=True)


def cargar_registros_cultivos(
    cultivos: list[int],
    ruta: Path = RUTA_MODELADO,
    unidad: str = "Tonelada",
    tamano_bloque: int = 150_000,
) -> pd.DataFrame:
    """Carga en una sola pasada solo los cultivos que seran entrenados."""
    seleccionados = {int(cultivo) for cultivo in cultivos}
    bloques = []
    for bloque in pd.read_csv(
        Path(ruta), usecols=COLUMNAS_BASE, dtype={"cvegeo": "string"},
        chunksize=tamano_bloque, low_memory=False,
    ):
        mascara = (
            bloque["Idcultivo"].isin(seleccionados)
            & bloque["Nomunidad"].eq(unidad)
            & bloque["registro_apto_modelado"].eq(True)  # noqa: E712
        )
        if mascara.any():
            bloques.append(bloque.loc[mascara].copy())
    if not bloques:
        raise ValueError("No se encontraron registros de los cultivos seleccionados.")
    return pd.concat(bloques, ignore_index=True)


def preparar_cultivo(
    datos_nacionales: pd.DataFrame,
    cultivo: int | str,
) -> pd.DataFrame:
    """Consolida una observacion modelable por municipio, ciclo y modalidad."""
    if isinstance(cultivo, (int, np.integer)) or str(cultivo).isdigit():
        datos = datos_nacionales.loc[
            datos_nacionales["Idcultivo"].eq(int(cultivo))
        ].copy()
    else:
        datos = datos_nacionales.loc[
            datos_nacionales["Nomcultivo_canonico"].eq(str(cultivo))
        ].copy()
    datos = datos.loc[datos["registro_apto_modelado"].eq(True)].copy()  # noqa: E712
    if datos.empty:
        raise ValueError(f"No hay registros aptos para el cultivo {cultivo!r}.")
    numericas = ["Cosechada", "Volumenproduccion", *VARIABLES_NUMERICAS]
    datos[numericas] = datos[numericas].apply(pd.to_numeric, errors="coerce")
    claves = [
        "cvegeo", "Anio", "Idcultivo", "Idciclo", "Idmodalidad",
        "Idunidadmedida",
    ]
    datos = datos.groupby(claves, as_index=False, observed=True, dropna=False).agg(
        Nomestado=("Nomestado_canonico", "first"),
        Nommunicipio=("Nommunicipio_canonico", "first"),
        Nomcultivo=("Nomcultivo_canonico", "first"),
        Nomcicloproductivo=("Nomcicloproductivo", "first"),
        Nommodalidad=("Nommodalidad", "first"),
        Nomunidad=("Nomunidad", "first"),
        Cosechada=("Cosechada", "sum"), Volumenproduccion=("Volumenproduccion", "sum"),
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
    datos[OBJETIVO] = datos["Volumenproduccion"] / datos["Cosechada"]
    # Alias legible para consumidores anteriores y tablas de resultados.
    datos["Rendimiento"] = datos[OBJETIVO]
    datos = datos.replace([np.inf, -np.inf], np.nan)
    datos = datos.loc[
        datos["Cosechada"].gt(0) & datos[OBJETIVO].gt(0)
        & datos[OBJETIVO].notna()
    ].copy()
    for columna in VARIABLES_CATEGORICAS:
        datos[columna] = datos[columna].astype("string").fillna("Sin informacion")
    # El historial usa exclusivamente anos anteriores y por construccion es nulo
    # al inicio de cada serie. Se conserva: el pipeline lo imputa dentro de cada
    # particion, sin descartar justamente los primeros anos del cultivo.
    numericas_obligatorias = [
        columna for columna in VARIABLES_NUMERICAS
        if columna not in VARIABLES_HISTORICAS
    ]
    return datos.dropna(subset=numericas_obligatorias).reset_index(drop=True)


def separar_xy(datos: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    variables = [*VARIABLES_NUMERICAS, *VARIABLES_CATEGORICAS]
    return datos[variables].copy(), datos[OBJETIVO].copy()
