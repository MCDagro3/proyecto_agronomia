"""Funciones de integración espacial y climática para el proyecto agronómico."""
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree


def crear_clave_municipal(df):
    """Agrega cvegeo (2 dígitos entidad + 3 municipio) sin modificar el origen."""
    resultado = df.copy()
    resultado["cvegeo"] = (
        resultado["Idestado"].astype(int).astype(str).str.zfill(2)
        + resultado["Idmunicipio"].astype(int).astype(str).str.zfill(3)
    )
    return resultado


def puntos_representativos_municipales(gdf_inegi):
    """Genera puntos interiores por municipio, en EPSG:4326."""
    gdf = gdf_inegi[["cvegeo", "nomgeo", "geometry"]].copy()
    gdf["cvegeo"] = gdf["cvegeo"].astype("string").str.zfill(5)
    if gdf["cvegeo"].duplicated().any():
        raise ValueError("INEGI contiene claves municipales duplicadas")
    if gdf.crs is None:
        raise ValueError("INEGI no tiene CRS definido")
    proyectado = gdf.to_crs("EPSG:6372")
    proyectado["geometry"] = proyectado.geometry.representative_point()
    puntos = proyectado.to_crs("EPSG:4326")
    puntos["latitud"] = puntos.geometry.y
    puntos["longitud"] = puntos.geometry.x
    return puntos


def asignar_estaciones_cercanas(puntos_municipales, estaciones_clima, claves_agricolas=None, k=3):
    """Obtiene k estaciones por municipio usando distancia Haversine (km)."""
    municipios = puntos_municipales[["cvegeo", "nomgeo", "latitud", "longitud"]].copy()
    if claves_agricolas is not None:
        municipios = municipios[municipios["cvegeo"].isin(claves_agricolas)].copy()
    estaciones = estaciones_clima[["estacion", "nombre", "latitud", "longitud"]].dropna().copy()
    if municipios.empty or estaciones.empty:
        raise ValueError("No hay municipios o estaciones con coordenadas")
    if municipios["cvegeo"].duplicated().any() or estaciones["estacion"].duplicated().any():
        raise ValueError("Hay claves duplicadas en municipios o estaciones")
    if k < 1 or k > len(estaciones):
        raise ValueError("k fuera de rango")
    coords_m = np.radians(municipios[["latitud", "longitud"]].to_numpy(dtype=float))
    coords_e = np.radians(estaciones[["latitud", "longitud"]].to_numpy(dtype=float))
    dist, idx = BallTree(coords_e, metric="haversine").query(coords_m, k=k)
    registros = []
    for i, mun in enumerate(municipios.itertuples(index=False)):
        for j in range(k):
            est = estaciones.iloc[idx[i, j]]
            registros.append({"cvegeo": mun.cvegeo, "municipio": mun.nomgeo,
                             "estacion": est["estacion"], "nombre_estacion": est["nombre"],
                             "orden_cercania": j + 1, "distancia_km": float(dist[i, j] * 6371.0088)})
    return pd.DataFrame(registros)


def interpolar_clima_municipal(df_proximidad, df_clima_anual, radio_max_km=100, potencia=2):
    """IDW anual de precipitación y temperatura; sin imputar años sin datos."""
    if potencia <= 0 or radio_max_km <= 0:
        raise ValueError("Radio y potencia deben ser positivos")
    clima = df_clima_anual.copy()
    if clima.duplicated(["estacion", "anio"]).any():
        raise ValueError("Clima tiene duplicados estación-año")
    prox = df_proximidad.loc[df_proximidad["distancia_km"] <= radio_max_km].copy()
    combinado = prox.merge(clima, on="estacion", how="left", validate="many_to_many")
    # Una coincidencia exacta debe prevalecer frente a estaciones distantes.
    combinado["peso"] = 1.0 / combinado["distancia_km"].clip(lower=0.001).pow(potencia)
    indice = pd.MultiIndex.from_product(
        [df_proximidad["cvegeo"].drop_duplicates(), sorted(clima["anio"].unique())],
        names=["cvegeo", "anio"])
    resultado = indice.to_frame(index=False)
    for indicador in ("precipitacion_anual_mm", "temperatura_media_c"):
        validos = combinado.loc[combinado[indicador].notna()].copy()
        validos["producto"] = validos[indicador] * validos["peso"]
        agregado = validos.groupby(["cvegeo", "anio"]).agg(
            numerador=("producto", "sum"), denominador=("peso", "sum"),
            n_estaciones=("estacion", "nunique"),
            distancia_min_km=("distancia_km", "min"),
        ).reset_index()
        agregado[indicador] = agregado["numerador"] / agregado["denominador"]
        agregado = agregado[["cvegeo", "anio", indicador, "n_estaciones", "distancia_min_km"]].rename(columns={
            "n_estaciones": f"estaciones_{indicador}",
            "distancia_min_km": f"distancia_min_{indicador}_km",
        })
        resultado = resultado.merge(agregado, on=["cvegeo", "anio"], how="left", validate="one_to_one")
        resultado[f"estaciones_{indicador}"] = resultado[f"estaciones_{indicador}"].fillna(0).astype(int)
    return resultado.sort_values(["cvegeo", "anio"]).reset_index(drop=True)


