"""Funciones para resumir la edafología por municipio."""

import geopandas as gpd
import pandas as pd

from datasets.edafologia import GRUPOS_SUELO_WRB

VALORES_SIN_CLASIFICACION = {"", "N", "N/A", "NA"}


def _categoria_dominante_por_superficie(
    intersecciones: gpd.GeoDataFrame,
    columna: str,
    nombre_salida: str,
    areas_municipales: pd.Series,
) -> pd.DataFrame:
    datos = intersecciones[["cvegeo", columna, "area_interseccion_m2"]].copy()
    datos[columna] = datos[columna].astype("string").str.strip()
    datos = datos.loc[datos[columna].notna() & ~datos[columna].isin(VALORES_SIN_CLASIFICACION)]
    superficies = datos.groupby(["cvegeo", columna], as_index=False, observed=True)[
        "area_interseccion_m2"
    ].sum()
    dominante = (
        superficies.sort_values(
            ["cvegeo", "area_interseccion_m2", columna],
            ascending=[True, False, True],
        )
        .drop_duplicates("cvegeo")
        .rename(columns={columna: nombre_salida})
    )
    dominante[f"{nombre_salida}_pct"] = (
        dominante["area_interseccion_m2"] / dominante["cvegeo"].map(areas_municipales) * 100
    ).round(2)
    return dominante.drop(columns="area_interseccion_m2")


def _composicion_por_superficie(
    intersecciones: gpd.GeoDataFrame,
    areas_municipales: pd.Series,
    columna: str = "Grupo1",
    prefijo: str = "suelo_pct_",
) -> pd.DataFrame:
    """Porcentaje del área municipal que ocupa cada grupo de suelo.

    Devuelve una columna por grupo (por ejemplo ``suelo_pct_LP``). Los grupos
    ausentes en un municipio valen 0. ``SA`` (suelo cubierto por agua) se
    trata como un grupo más.
    """
    datos = intersecciones[["cvegeo", columna, "area_interseccion_m2"]].copy()
    datos[columna] = datos[columna].astype("string").str.strip()
    datos = datos.loc[datos[columna].notna() & ~datos[columna].isin(VALORES_SIN_CLASIFICACION)]
    composicion = datos.pivot_table(
        index="cvegeo",
        columns=columna,
        values="area_interseccion_m2",
        aggfunc="sum",
        fill_value=0.0,
        observed=True,
    )
    composicion = (composicion.div(composicion.index.map(areas_municipales), axis=0) * 100).round(
        2
    )
    composicion = composicion[sorted(composicion.columns)]
    composicion.columns = [f"{prefijo}{grupo}" for grupo in composicion.columns]
    composicion.columns.name = None
    return composicion.reset_index()


def resumir_edafologia_municipal(
    municipios: gpd.GeoDataFrame,
    edafologia: gpd.GeoDataFrame,
    crs_areas: str = "EPSG:6372",
) -> pd.DataFrame:
    """Calcula categorías dominantes y composición de suelos por municipio."""
    if "cvegeo" not in municipios.columns:
        raise KeyError("La capa municipal no contiene 'cvegeo'.")
    requeridas = {"Grupo1", "Clase_tex"}
    faltantes = requeridas - set(edafologia.columns)
    if faltantes:
        raise KeyError(f"Faltan columnas edafológicas: {sorted(faltantes)}")
    if municipios.crs is None or edafologia.crs is None:
        raise ValueError("Ambas capas deben tener CRS definido.")

    municipios_area = municipios[["cvegeo", "geometry"]].copy()
    municipios_area["cvegeo"] = municipios_area["cvegeo"].astype("string").str.zfill(5)
    if municipios_area["cvegeo"].duplicated().any():
        raise ValueError("La capa municipal contiene cvegeo duplicadas.")
    municipios_area = municipios_area.to_crs(crs_areas)
    suelos = edafologia[[*sorted(requeridas), "geometry"]].to_crs(crs_areas)
    areas_municipales = municipios_area.set_index("cvegeo").geometry.area
    intersecciones = gpd.overlay(
        municipios_area,
        suelos,
        how="intersection",
        keep_geom_type=False,
    )
    intersecciones["area_interseccion_m2"] = intersecciones.geometry.area
    intersecciones = intersecciones.loc[intersecciones["area_interseccion_m2"].gt(0)]

    resultado = municipios_area[["cvegeo"]].copy()
    configuracion = {
        "Grupo1": "grupo_suelo_dominante",
        "Clase_tex": "textura_dominante",
    }
    for columna, salida in configuracion.items():
        resumen = _categoria_dominante_por_superficie(
            intersecciones, columna, salida, areas_municipales
        )
        resultado = resultado.merge(resumen, on="cvegeo", how="left", validate="one_to_one")

    grupos = intersecciones[["cvegeo", "Grupo1"]].copy()
    grupos["Grupo1"] = grupos["Grupo1"].astype("string").str.strip()
    grupos = grupos.loc[
        grupos["Grupo1"].notna() & ~grupos["Grupo1"].isin(VALORES_SIN_CLASIFICACION)
    ]
    diversidad = (
        grupos.groupby("cvegeo")["Grupo1"].nunique().rename("grupos_suelo_n").reset_index()
    )
    resultado = resultado.merge(diversidad, on="cvegeo", how="left", validate="one_to_one")
    composicion = _composicion_por_superficie(intersecciones, areas_municipales)
    resultado = resultado.merge(composicion, on="cvegeo", how="left", validate="one_to_one")
    columnas_composicion = [columna for columna in composicion.columns if columna != "cvegeo"]
    resultado[columnas_composicion] = resultado[columnas_composicion].fillna(0.0)
    resultado["nombre_suelo_wrb"] = resultado["grupo_suelo_dominante"].map(GRUPOS_SUELO_WRB)
    if resultado["cvegeo"].duplicated().any():
        raise AssertionError("El resumen edafológico produjo municipios duplicados.")
    return pd.DataFrame(resultado.drop(columns="geometry", errors="ignore"))
