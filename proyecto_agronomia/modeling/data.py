"""Carga del dataset nacional reducido para modelos de rendimiento."""

from pathlib import Path

import numpy as np
import pandas as pd

from proyecto_agronomia.config import INTERIM_DATA_DIR

RUTA_DATOS_MODELO = (
    INTERIM_DATA_DIR / "modeling" / "nacional"
    / "agricultura_modelado_pca_2003_2025.csv"
)
OBJETIVO = "Rendimiento"
COLUMNAS_CONTEXTO = [
    "cvegeo", "Anio", "Nomestado", "Nommunicipio", "Nomcultivo",
    "Nomcicloproductivo", "Nommodalidad", "Nomunidad", "Cosechada",
    "Volumenproduccion", OBJETIVO,
]


def columnas_componentes(ruta: Path = RUTA_DATOS_MODELO) -> list[str]:
    """Obtiene las columnas predictoras sin cargar las filas del CSV."""
    encabezado = pd.read_csv(Path(ruta), nrows=0).columns
    columnas = [c for c in encabezado if c.startswith("componente_")]
    if not columnas:
        raise ValueError("El dataset no contiene columnas componente_*.")
    return columnas


def preparar_datos_cultivo(
    cultivo: str,
    ruta: Path = RUTA_DATOS_MODELO,
    unidad: str | None = None,
    tamano_bloque: int = 150_000,
) -> tuple[pd.DataFrame, str]:
    """Lee por bloques y selecciona un cultivo del dataset PCA nacional."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el dataset modelado: {ruta}")
    componentes = columnas_componentes(ruta)
    usecols = [*COLUMNAS_CONTEXTO, *componentes]
    bloques = []
    for bloque in pd.read_csv(
        ruta, usecols=usecols, dtype={"cvegeo": "string"},
        chunksize=tamano_bloque, low_memory=False,
    ):
        seleccion = bloque.loc[bloque["Nomcultivo"].eq(cultivo)]
        if not seleccion.empty:
            bloques.append(seleccion)
    if not bloques:
        raise ValueError(f"No existen registros para el cultivo {cultivo!r}.")
    datos = pd.concat(bloques, ignore_index=True)
    datos["cvegeo"] = datos["cvegeo"].str.zfill(5)
    if unidad is None:
        superficie = datos.groupby("Nomunidad", observed=True)["Cosechada"].sum()
        unidad = str(superficie.idxmax())
    datos = datos.loc[datos["Nomunidad"].eq(unidad)].copy()
    if datos.empty:
        raise ValueError(f"No hay registros de {cultivo!r} con unidad {unidad!r}.")

    claves = [
        "cvegeo", "Anio", "Nomcultivo", "Nomcicloproductivo",
        "Nommodalidad", "Nomunidad",
    ]
    agregaciones = {
        "Nomestado": "first", "Nommunicipio": "first",
        "Cosechada": "sum", "Volumenproduccion": "sum",
        **{columna: "first" for columna in componentes},
    }
    datos = datos.groupby(
        claves, as_index=False, observed=True, dropna=False
    ).agg(agregaciones)
    datos[OBJETIVO] = datos["Volumenproduccion"] / datos["Cosechada"]
    datos = datos.replace([np.inf, -np.inf], np.nan)
    datos = datos.loc[
        datos["Cosechada"].gt(0)
        & datos[OBJETIVO].gt(0)
        & datos[OBJETIVO].notna()
    ].reset_index(drop=True)
    return datos, unidad


def separar_xy(datos: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Usa exclusivamente componentes como predictores."""
    variables = [c for c in datos.columns if c.startswith("componente_")]
    if not variables:
        raise ValueError("No se encontraron predictores componente_*.")
    return datos[variables].copy(), datos[OBJETIVO].copy()
