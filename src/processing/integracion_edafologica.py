"""Funciones para resumir la edafología por municipio o por área agrícola."""

from collections.abc import Mapping

import geopandas as gpd
import pandas as pd

from datasets.edafologia import GRUPOS_SUELO_WRB
from datasets.mapbiomas import RESPALDOS_MASCARA

VALORES_SIN_CLASIFICACION = {"", "N", "N/A", "NA"}


def _filtrar_clasificados(datos: pd.DataFrame, columna: str) -> pd.DataFrame:
    datos = datos.copy()
    datos[columna] = datos[columna].astype("string").str.strip()
    return datos.loc[datos[columna].notna() & ~datos[columna].isin(VALORES_SIN_CLASIFICACION)]


def _alinear_denominador(
    tabla: pd.DataFrame, denominadores: pd.Series, llaves: list[str]
) -> pd.Series:
    """Denominador de cada fila de ``tabla`` según sus ``llaves``."""
    indice = pd.MultiIndex.from_frame(tabla[llaves]) if len(llaves) > 1 else tabla[llaves[0]]
    return pd.Series(denominadores.reindex(indice).to_numpy(), index=tabla.index)


def _categoria_dominante_por_superficie(
    intersecciones: pd.DataFrame,
    columna: str,
    nombre_salida: str,
    denominadores: pd.Series,
    llaves: list[str] | None = None,
    columna_area: str = "area_interseccion_m2",
) -> pd.DataFrame:
    """Categoría con más superficie por llave y su porcentaje del denominador.

    ``denominadores`` es una serie indexada por ``llaves`` (por omisión
    ``cvegeo`` con el área municipal; con MapBiomas, ``cvegeo, Anio, mascara``
    con el área de la máscara agrícola).
    """
    llaves = llaves or ["cvegeo"]
    datos = _filtrar_clasificados(intersecciones[[*llaves, columna, columna_area]], columna)
    superficies = datos.groupby([*llaves, columna], as_index=False, observed=True)[
        columna_area
    ].sum()
    dominante = (
        superficies.sort_values(
            [*llaves, columna_area, columna],
            ascending=[True] * len(llaves) + [False, True],
        )
        .drop_duplicates(llaves)
        .rename(columns={columna: nombre_salida})
    )
    dominante[f"{nombre_salida}_pct"] = (
        dominante[columna_area] / _alinear_denominador(dominante, denominadores, llaves) * 100
    ).round(2)
    return dominante.drop(columns=columna_area)


def _composicion_por_superficie(
    intersecciones: pd.DataFrame,
    denominadores: pd.Series,
    columna: str = "Grupo1",
    prefijo: str = "suelo_pct_",
    llaves: list[str] | None = None,
    columna_area: str = "area_interseccion_m2",
) -> pd.DataFrame:
    """Porcentaje del denominador que ocupa cada grupo de suelo.

    Devuelve una columna por grupo (por ejemplo ``suelo_pct_LP``). Los grupos
    ausentes valen 0. ``SA`` (suelo cubierto por agua) se trata como un grupo
    más.
    """
    llaves = llaves or ["cvegeo"]
    datos = _filtrar_clasificados(intersecciones[[*llaves, columna, columna_area]], columna)
    composicion = datos.pivot_table(
        index=llaves,
        columns=columna,
        values=columna_area,
        aggfunc="sum",
        fill_value=0.0,
        observed=True,
    )
    composicion = (
        composicion.div(denominadores.reindex(composicion.index).to_numpy(), axis=0) * 100
    ).round(2)
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


LLAVES_MASCARA = ["cvegeo", "Anio", "mascara"]
COLUMNAS_SUELO = [
    "grupo_suelo_dominante",
    "grupo_suelo_dominante_pct",
    "textura_dominante",
    "textura_dominante_pct",
    "grupos_suelo_n",
    "nombre_suelo_wrb",
]


def resumir_edafologia_por_mascara(
    conteos: pd.DataFrame,
    resumen_municipal: pd.DataFrame,
    llaves_requeridas: pd.DataFrame,
    umbral_ha: float = 1.0,
    respaldos: Mapping[str, str] = RESPALDOS_MASCARA,
) -> pd.DataFrame:
    """Resumen edafológico sobre el área agrícola (máscara MapBiomas).

    Parameters
    ----------
    conteos
        Salida de ``contar_suelo_por_mascara``: ``cvegeo, Anio, mascara,
        Grupo1, Clase_tex, area_m2``.
    resumen_municipal
        Salida de :func:`resumir_edafologia_municipal`, usada como respaldo.
    llaves_requeridas
        Combinaciones ``cvegeo, Anio, mascara`` presentes en los datos
        agrícolas; el resultado tiene exactamente una fila por cada una.
    umbral_ha
        Área mínima (ha) para usar la composición de una máscara.
    respaldos
        Máscara del registro -> máscara auxiliar a usar si la propia mide menos
        de ``umbral_ha`` (p. ej. ``perenne`` -> ``agricola``, clases 19+36).

    Returns
    -------
    pd.DataFrame
        Mismas columnas que el resumen municipal, calculadas como % del área de
        referencia, más ``area_mascara_ha`` (área de la máscara propia del
        registro) y ``suelo_fuente``: ``"mascara"`` (máscara propia), el nombre
        de la máscara de respaldo (``"agricola"``) o ``"municipal"`` (municipio
        completo, cuando ninguna máscara alcanza el umbral).
    """
    llaves = LLAVES_MASCARA
    datos = conteos.rename(columns={"area_m2": "area_interseccion_m2"}).copy()
    datos["cvegeo"] = datos["cvegeo"].astype("string").str.zfill(5)
    datos["mascara"] = datos["mascara"].astype("string")
    datos["Anio"] = datos["Anio"].astype("int64")
    datos["Clase_tex"] = pd.to_numeric(datos["Clase_tex"], errors="coerce").astype("Int64")
    denominadores = datos.groupby(llaves)["area_interseccion_m2"].sum()

    resultado = denominadores.rename("area_mascara_ha").div(1e4).round(2).reset_index()
    for columna, salida in {
        "Grupo1": "grupo_suelo_dominante",
        "Clase_tex": "textura_dominante",
    }.items():
        resumen = _categoria_dominante_por_superficie(
            datos, columna, salida, denominadores, llaves=llaves
        )
        resultado = resultado.merge(resumen, on=llaves, how="left", validate="one_to_one")
    diversidad = (
        _filtrar_clasificados(datos.loc[datos["area_interseccion_m2"].gt(0)], "Grupo1")
        .groupby(llaves)["Grupo1"]
        .nunique()
        .rename("grupos_suelo_n")
        .reset_index()
    )
    resultado = resultado.merge(diversidad, on=llaves, how="left", validate="one_to_one")
    composicion = _composicion_por_superficie(datos, denominadores, llaves=llaves)
    resultado = resultado.merge(composicion, on=llaves, how="left", validate="one_to_one")

    columnas_pct = sorted(
        {c for c in [*resultado.columns, *resumen_municipal.columns] if c.startswith("suelo_pct_")}
    )
    for columna in columnas_pct:
        if columna not in resultado:
            resultado[columna] = 0.0
    resultado[columnas_pct] = resultado[columnas_pct].fillna(0.0)
    resultado["nombre_suelo_wrb"] = resultado["grupo_suelo_dominante"].map(GRUPOS_SUELO_WRB)

    # Una fila por combinación agrícola; respaldo municipal donde no hay máscara.
    base = llaves_requeridas[llaves].drop_duplicates().copy()
    base["cvegeo"] = base["cvegeo"].astype("string").str.zfill(5)
    base["Anio"] = base["Anio"].astype("int64")
    base["mascara"] = base["mascara"].astype("string")
    final = base.merge(resultado, on=llaves, how="left", validate="one_to_one")
    final["area_mascara_ha"] = final["area_mascara_ha"].fillna(0.0)
    respaldo = final["area_mascara_ha"].lt(umbral_ha) | final["grupo_suelo_dominante"].isna()
    fuente = pd.Series("mascara", index=final.index, dtype="object")
    columnas_valor = [*COLUMNAS_SUELO, *columnas_pct]
    for columna in columnas_valor:
        final[columna] = final[columna].astype("object")

    # Primer respaldo: otra máscara del mismo municipio y año (perenne -> agrícola).
    mascara_respaldo = final["mascara"].map(dict(respaldos))
    candidatos = respaldo & mascara_respaldo.notna()
    if candidatos.any():
        alternativa = (
            final.loc[candidatos, ["cvegeo", "Anio"]]
            .assign(mascara=mascara_respaldo[candidatos].astype("string").to_numpy())
            .merge(resultado, on=llaves, how="left", validate="many_to_one")
            .set_index(final.index[candidatos])
        )
        usar = (
            alternativa["area_mascara_ha"].ge(umbral_ha)
            & alternativa["grupo_suelo_dominante"].notna()
        )
        indices = usar[usar].index
        final.loc[indices, columnas_valor] = alternativa.loc[indices, columnas_valor]
        fuente[indices] = mascara_respaldo[indices]
        respaldo[indices] = False

    municipal = resumen_municipal.copy()
    municipal["cvegeo"] = municipal["cvegeo"].astype("string").str.zfill(5)
    for columna in columnas_pct:
        if columna not in municipal:
            municipal[columna] = 0.0
    valores_municipales = (
        final.loc[respaldo, ["cvegeo"]]
        .merge(municipal[["cvegeo", *columnas_valor]], on="cvegeo", how="left")
        .set_index(final.index[respaldo])
    )
    for columna in columnas_valor:
        final.loc[respaldo, columna] = valores_municipales[columna]
    fuente[respaldo] = "municipal"
    final["suelo_fuente"] = pd.Categorical(
        fuente, categories=["mascara", *sorted(set(respaldos.values())), "municipal"]
    )
    final["textura_dominante"] = pd.to_numeric(final["textura_dominante"], errors="coerce")
    for columna in [
        "grupo_suelo_dominante_pct",
        "textura_dominante_pct",
        *columnas_pct,
    ]:
        final[columna] = pd.to_numeric(final[columna], errors="coerce")
    final["grupos_suelo_n"] = pd.to_numeric(final["grupos_suelo_n"], errors="coerce").astype(
        "Int64"
    )
    for columna in ["grupo_suelo_dominante", "nombre_suelo_wrb"]:
        final[columna] = final[columna].astype("string")
    if final.duplicated(llaves).any():
        raise AssertionError("El resumen por máscara produjo llaves duplicadas.")
    return final[[*llaves, *COLUMNAS_SUELO, *columnas_pct, "area_mascara_ha", "suelo_fuente"]]
