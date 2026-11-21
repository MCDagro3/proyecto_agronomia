"""Funciones de integración espacial y climática para el proyecto agronómico."""
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree


NOMBRES_MESES = {
    1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun",
    7: "jul", 8: "ago", 9: "sep", 10: "oct", 11: "nov", 12: "dic",
}


def crear_clave_municipal(df):
    """Agrega cvegeo (2 dígitos entidad + 3 municipio) sin modificar el origen."""
    resultado = df.copy()
    resultado["cvegeo"] = (
        resultado["Idestado"].astype(int).astype(str).str.zfill(2)
        + resultado["Idmunicipio"].astype(int).astype(str).str.zfill(3)
    )
    return resultado


def validar_clima_mensual(
    clima: pd.DataFrame,
    anio_inicial: int = 2002,
    anio_final: int = 2025,
) -> pd.DataFrame:
    """Valida llave, cobertura temporal y completitud del clima NASA mensual."""
    requeridas = {
        "cvegeo", "anio", "mes", "temperatura_media_mes_c",
        "precipitacion_mes_mm", "dias_esperados", "dias_temperatura",
        "dias_precipitacion",
    }
    faltantes = requeridas - set(clima.columns)
    if faltantes:
        raise KeyError(f"Faltan columnas climáticas: {sorted(faltantes)}")
    resultado = clima.copy()
    resultado["cvegeo"] = resultado["cvegeo"].astype("string").str.zfill(5)
    clave = ["cvegeo", "anio", "mes"]
    if resultado.duplicated(clave).any():
        raise ValueError("El clima mensual contiene llaves duplicadas.")
    if set(resultado["mes"].dropna().unique()) != set(range(1, 13)):
        raise ValueError("La cobertura mensual no contiene exactamente los meses 1-12.")
    esperados = set(range(anio_inicial, anio_final + 1))
    encontrados = set(resultado["anio"].dropna().unique())
    if encontrados != esperados:
        raise ValueError(
            f"Cobertura anual inesperada; faltan={sorted(esperados-encontrados)}, "
            f"sobran={sorted(encontrados-esperados)}"
        )
    indicadores = ["temperatura_media_mes_c", "precipitacion_mes_mm"]
    if resultado[indicadores].isna().any().any():
        raise ValueError("Existen valores climáticos mensuales nulos.")
    if not resultado["dias_temperatura"].eq(resultado["dias_esperados"]).all():
        raise ValueError("Existen meses incompletos de temperatura.")
    if not resultado["dias_precipitacion"].eq(resultado["dias_esperados"]).all():
        raise ValueError("Existen meses incompletos de precipitación.")
    return resultado.sort_values(clave).reset_index(drop=True)


def construir_clima_mensual_ancho(clima: pd.DataFrame) -> pd.DataFrame:
    """Convierte los meses actuales y octubre-diciembre anteriores en columnas."""
    indice = ["cvegeo", "anio"]
    temperatura = clima.pivot(
        index=indice, columns="mes", values="temperatura_media_mes_c"
    ).rename(columns={m: f"temperatura_{n}_c" for m, n in NOMBRES_MESES.items()})
    precipitacion = clima.pivot(
        index=indice, columns="mes", values="precipitacion_mes_mm"
    ).rename(columns={m: f"precipitacion_{n}_mm" for m, n in NOMBRES_MESES.items()})
    anteriores = clima.loc[clima["mes"].isin([10, 11, 12])].copy()
    anteriores["anio"] += 1
    temperatura_anterior = anteriores.pivot(
        index=indice, columns="mes", values="temperatura_media_mes_c"
    ).rename(
        columns={m: f"temperatura_{NOMBRES_MESES[m]}_anterior_c" for m in [10, 11, 12]}
    )
    precipitacion_anterior = anteriores.pivot(
        index=indice, columns="mes", values="precipitacion_mes_mm"
    ).rename(
        columns={
            m: f"precipitacion_{NOMBRES_MESES[m]}_anterior_mm"
            for m in [10, 11, 12]
        }
    )
    return (
        temperatura.join(precipitacion, validate="one_to_one")
        .join(temperatura_anterior, validate="one_to_one")
        .join(precipitacion_anterior, validate="one_to_one")
        .reset_index()
    )


def resumir_clima_por_ciclo(clima: pd.DataFrame) -> pd.DataFrame:
    """Resume temperatura ponderada y precipitación según el ciclo productivo."""
    columnas = [
        "cvegeo", "anio", "temperatura_media_mes_c",
        "precipitacion_mes_mm", "dias_esperados",
    ]
    oi_actual = clima.loc[clima["mes"].isin([1, 2, 3]), columnas].copy()
    oi_actual["Nomcicloproductivo"] = "Otoño-Invierno"
    oi_anterior = clima.loc[clima["mes"].isin([10, 11, 12]), columnas].copy()
    oi_anterior["anio"] += 1
    oi_anterior["Nomcicloproductivo"] = "Otoño-Invierno"
    primavera_verano = clima.loc[clima["mes"].between(4, 9), columnas].copy()
    primavera_verano["Nomcicloproductivo"] = "Primavera-Verano"
    perennes = clima[columnas].copy()
    perennes["Nomcicloproductivo"] = "Perennes"
    ventanas = pd.concat(
        [oi_anterior, oi_actual, primavera_verano, perennes], ignore_index=True
    )
    ventanas["temperatura_por_dias"] = (
        ventanas["temperatura_media_mes_c"] * ventanas["dias_esperados"]
    )
    resumen = ventanas.groupby(
        ["cvegeo", "anio", "Nomcicloproductivo"], as_index=False
    ).agg(
        temperatura_por_dias=("temperatura_por_dias", "sum"),
        precipitacion_ciclo_mm=("precipitacion_mes_mm", "sum"),
        dias_clima_ciclo=("dias_esperados", "sum"),
    )
    resumen["temperatura_media_ciclo_c"] = (
        resumen.pop("temperatura_por_dias") / resumen["dias_clima_ciclo"]
    )
    return resumen


def integrar_agricultura_clima(
    agricultura: pd.DataFrame,
    clima_ciclos: pd.DataFrame,
    clima_ancho: pd.DataFrame,
) -> pd.DataFrame:
    """Añade clima por ciclo y por mes sin multiplicar registros agrícolas."""
    resultado = agricultura.merge(
        clima_ciclos,
        left_on=["cvegeo", "Anio", "Nomcicloproductivo"],
        right_on=["cvegeo", "anio", "Nomcicloproductivo"],
        how="left",
        validate="many_to_one",
    ).drop(columns="anio")
    resultado = resultado.merge(
        clima_ancho,
        left_on=["cvegeo", "Anio"],
        right_on=["cvegeo", "anio"],
        how="left",
        validate="many_to_one",
    ).drop(columns="anio")
    if len(resultado) != len(agricultura):
        raise AssertionError("La integración climática alteró el número de registros.")
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


