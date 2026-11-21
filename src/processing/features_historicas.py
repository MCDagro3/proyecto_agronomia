"""Caracteristicas historicas de rendimiento calculadas sin fuga temporal."""

import numpy as np
import pandas as pd


CLAVES_HISTORIA = [
    "cvegeo", "Nomcultivo", "Nomcicloproductivo", "Nommodalidad", "Nomunidad",
]
COLUMNAS_HISTORICAS = [
    "rendimiento_hist_anios",
    "rendimiento_anio_anterior",
    "rendimiento_hist_media",
    "rendimiento_hist_desviacion",
    "rendimiento_hist_cv",
]


def agregar_historial_rendimiento(
    datos: pd.DataFrame,
    minimo_periodos: int = 3,
) -> pd.DataFrame:
    """Agrega estadisticas que para el año t usan solamente años anteriores."""
    requeridas = {
        *CLAVES_HISTORIA, "Anio", "Cosechada", "Volumenproduccion",
    }
    faltantes = requeridas - set(datos.columns)
    if faltantes:
        raise KeyError(f"Faltan columnas para historial: {sorted(faltantes)}")
    if minimo_periodos < 2:
        raise ValueError("minimo_periodos debe ser al menos 2.")

    salida = datos.copy()
    salida["cvegeo"] = salida["cvegeo"].astype("string").str.zfill(5)
    for columna in ["Anio", "Cosechada", "Volumenproduccion"]:
        salida[columna] = pd.to_numeric(salida[columna], errors="coerce")

    claves_anuales = [*CLAVES_HISTORIA, "Anio"]
    anual = (
        salida.groupby(claves_anuales, as_index=False, observed=True, dropna=False)
        .agg(
            Cosechada=("Cosechada", "sum"),
            Volumenproduccion=("Volumenproduccion", "sum"),
        )
        .sort_values([*CLAVES_HISTORIA, "Anio"])
    )
    anual["rendimiento_anual"] = (
        anual["Volumenproduccion"] / anual["Cosechada"]
    ).where(anual["Cosechada"].gt(0))
    anual["rendimiento_anual"] = anual["rendimiento_anual"].replace(
        [np.inf, -np.inf], np.nan
    )
    grupos = anual.groupby(CLAVES_HISTORIA, observed=True, dropna=False)
    anual["rendimiento_hist_anios"] = grupos.cumcount()
    anual["rendimiento_anio_anterior"] = grupos["rendimiento_anual"].shift(1)
    anual["rendimiento_hist_media"] = grupos["rendimiento_anual"].transform(
        lambda serie: serie.shift(1).expanding(min_periods=minimo_periodos).mean()
    )
    anual["rendimiento_hist_desviacion"] = grupos["rendimiento_anual"].transform(
        lambda serie: serie.shift(1).expanding(min_periods=minimo_periodos).std()
    )
    anual["rendimiento_hist_cv"] = (
        anual["rendimiento_hist_desviacion"] / anual["rendimiento_hist_media"]
    ).replace([np.inf, -np.inf], np.nan)

    caracteristicas = anual[[*claves_anuales, *COLUMNAS_HISTORICAS]]
    resultado = salida.merge(
        caracteristicas,
        on=claves_anuales,
        how="left",
        validate="many_to_one",
    )
    if len(resultado) != len(datos):
        raise AssertionError("Las caracteristicas historicas alteraron los registros.")
    return resultado
