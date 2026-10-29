"""Descarga y agregación anual de NASA POWER (2023–2025) por municipio.

Entradas: DataFrame con cvegeo, Latitud, Longitud.
Salida: CSV municipal anual con precipitación y temperatura.
"""
from __future__ import annotations

import logging
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from proyecto_agronomia.config import (
    NASA_POWER_ANIO_FINAL,
    NASA_POWER_ANIO_INICIAL,
    NASA_POWER_COMMUNITY,
    NASA_POWER_FORMAT,
    NASA_POWER_MAX_REINTENTOS,
    NASA_POWER_PARAMETROS,
    NASA_POWER_PAUSA,
    NASA_POWER_PROCESSED_DIR,
    NASA_POWER_RAW_DIR,
    NASA_POWER_TIMEOUT,
    NASA_POWER_URL,
)

LOGGER = logging.getLogger(__name__)
PARAMETROS = tuple(NASA_POWER_PARAMETROS)


def consultar_nasa_power(latitud: float, longitud: float, inicio: int = NASA_POWER_ANIO_INICIAL,
                         fin: int = NASA_POWER_ANIO_FINAL, sesion: requests.Session | None = None,
                         max_reintentos: int = NASA_POWER_MAX_REINTENTOS) -> dict:
    """Consulta datos diarios: T2M (°C) y PRECTOTCORR (mm/día)."""
    parametros = {
        "parameters": ",".join(PARAMETROS), "community": NASA_POWER_COMMUNITY,
        "latitude": float(latitud), "longitude": float(longitud),
        "start": f"{inicio}0101", "end": f"{fin}1231", "format": NASA_POWER_FORMAT,
    }
    cliente = sesion or requests
    for intento in range(max_reintentos):
        try:
            respuesta = cliente.get(NASA_POWER_URL, params=parametros, timeout=NASA_POWER_TIMEOUT)
            if respuesta.status_code in (429, 500, 502, 503, 504):
                if intento == max_reintentos - 1:
                    respuesta.raise_for_status()
                espera = respuesta.headers.get("Retry-After", "")
                try:
                    segundos = min(float(espera), 300) if espera else min(10 * (2 ** intento), 300)
                except ValueError:
                    segundos = min(10 * (2 ** intento), 300)
                LOGGER.warning("NASA POWER HTTP %s; esperando %.1f s", respuesta.status_code, segundos)
                time.sleep(segundos + random.uniform(0, 1))
                continue
            respuesta.raise_for_status()
            datos = respuesta.json()
            if "properties" not in datos or "parameter" not in datos["properties"]:
                raise ValueError("Respuesta NASA POWER sin properties.parameter")
            return datos
        except (requests.Timeout, requests.ConnectionError):
            if intento == max_reintentos - 1:
                raise
            time.sleep(min(10 * (2 ** intento), 300))
    raise RuntimeError("No se pudo completar la consulta NASA POWER")


def resumir_nasa_power(datos: dict, cvegeo: str, inicio: int = NASA_POWER_ANIO_INICIAL,
                       fin: int = NASA_POWER_ANIO_FINAL) -> pd.DataFrame:
    """Agrega días válidos a años completos; si falta un día, deja NaN."""
    valores = datos["properties"]["parameter"]
    series = {}
    for variable in PARAMETROS:
        if variable not in valores:
            raise ValueError(f"Falta variable {variable} en respuesta NASA POWER")
        serie = pd.Series(valores[variable], dtype="float64")
        serie.index = pd.to_datetime(serie.index, format="%Y%m%d", errors="raise")
        series[variable] = serie.replace(-999, np.nan)
    diario = pd.DataFrame(series).sort_index()
    filas = []
    for anio in range(inicio, fin + 1):
        dias = diario.loc[diario.index.year == anio]
        esperados = 366 if pd.Timestamp(f"{anio}-12-31").is_leap_year else 365
        t = dias["T2M"]
        p = dias["PRECTOTCORR"]
        filas.append({
            "cvegeo": str(cvegeo).zfill(5), "anio": anio,
            "precipitacion_anual_mm": float(p.sum()) if len(dias) == esperados and p.notna().sum() == esperados else np.nan,
            "temperatura_media_c": float(t.mean()) if len(dias) == esperados and t.notna().sum() == esperados else np.nan,
            "dias_precipitacion": int(p.notna().sum()),
            "dias_temperatura": int(t.notna().sum()),
            "fuente": "NASA POWER",
        })
    return pd.DataFrame(filas)


def descargar_clima_nasa_por_celdas(
    municipios: pd.DataFrame,
    inicio: int,
    fin: int,
    pausa: float = NASA_POWER_PAUSA,
    resolucion_latitud: float = 0.5,
    resolucion_longitud: float = 0.625,
) -> pd.DataFrame:
    """Descarga NASA POWER una vez por celda y replica el clima a sus municipios.

    La cuadrícula usada por los parámetros meteorológicos de MERRA-2 es de
    0.5 grados de latitud por 0.625 grados de longitud. Los JSON por celda
    permiten reanudar la descarga sin repetir solicitudes ya completadas.
    """
    requeridas = {"cvegeo", "Latitud", "Longitud"}
    faltantes = requeridas - set(municipios.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas: {sorted(faltantes)}")
    if inicio > fin:
        raise ValueError("El año inicial no puede ser mayor que el año final")
    if pausa < 0:
        raise ValueError("La pausa no puede ser negativa")
    if resolucion_latitud <= 0 or resolucion_longitud <= 0:
        raise ValueError("Las resoluciones de la cuadrícula deben ser positivas")

    base = municipios.copy()
    base["cvegeo"] = base["cvegeo"].astype("string").str.zfill(5)
    if not base["cvegeo"].str.fullmatch(r"\d{5}", na=False).all():
        raise ValueError("cvegeo debe contener exactamente cinco dígitos")
    base = base.drop_duplicates("cvegeo").copy()
    base[["Latitud", "Longitud"]] = base[["Latitud", "Longitud"]].apply(
        pd.to_numeric, errors="coerce"
    )
    if base[["Latitud", "Longitud"]].isna().any().any():
        raise ValueError("Hay coordenadas municipales faltantes/no válidas")
    if not base["Latitud"].between(-90, 90).all():
        raise ValueError("Hay latitudes fuera del intervalo [-90, 90]")
    if not base["Longitud"].between(-180, 180).all():
        raise ValueError("Hay longitudes fuera del intervalo [-180, 180]")

    # Los índices enteros producen identificadores estables y nombres de
    # archivo seguros, incluso para coordenadas negativas.
    base["indice_celda_lat"] = np.rint(
        base["Latitud"] / resolucion_latitud
    ).astype(int)
    base["indice_celda_lon"] = np.rint(
        base["Longitud"] / resolucion_longitud
    ).astype(int)
    base["celda_lat"] = base["indice_celda_lat"] * resolucion_latitud
    base["celda_lon"] = base["indice_celda_lon"] * resolucion_longitud

    NASA_POWER_RAW_DIR.mkdir(parents=True, exist_ok=True)
    NASA_POWER_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    grupos = list(base.groupby(["indice_celda_lat", "indice_celda_lon"], sort=True))
    tablas = []

    LOGGER.info(
        "NASA POWER %s-%s: %s municipios agrupados en %s celdas",
        inicio,
        fin,
        len(base),
        len(grupos),
    )
    with requests.Session() as sesion:
        for numero, ((indice_lat, indice_lon), grupo) in enumerate(grupos, 1):
            celda_lat = float(grupo["celda_lat"].iloc[0])
            celda_lon = float(grupo["celda_lon"].iloc[0])
            archivo = NASA_POWER_RAW_DIR / (
                f"nasa_celda_lat{indice_lat}_lon{indice_lon}_{inicio}_{fin}.json"
            )
            if archivo.exists():
                import json

                with archivo.open("r", encoding="utf-8") as f:
                    datos = json.load(f)
            else:
                datos = consultar_nasa_power(
                    celda_lat,
                    celda_lon,
                    inicio,
                    fin,
                    sesion,
                )
                import json

                temporal = archivo.with_suffix(".tmp")
                with temporal.open("w", encoding="utf-8") as f:
                    json.dump(datos, f)
                temporal.replace(archivo)
                time.sleep(pausa)

            resumen_celda = resumir_nasa_power(datos, "00000", inicio, fin).drop(
                columns="cvegeo"
            )
            claves = grupo[["cvegeo"]].drop_duplicates().copy()
            claves["_union"] = 1
            resumen_celda["_union"] = 1
            tabla = claves.merge(resumen_celda, on="_union", validate="many_to_many").drop(
                columns="_union"
            )
            tabla["celda_lat"] = celda_lat
            tabla["celda_lon"] = celda_lon
            tablas.append(tabla)

            if numero % 25 == 0 or numero == len(grupos):
                LOGGER.info("Procesadas %s/%s celdas", numero, len(grupos))

    resultado = pd.concat(tablas, ignore_index=True) if tablas else pd.DataFrame()
    if not resultado.empty:
        resultado = resultado.sort_values(["cvegeo", "anio"]).reset_index(drop=True)
        if resultado.duplicated(["cvegeo", "anio"]).any():
            raise ValueError("La descarga generó claves municipio-año duplicadas")
        destino = NASA_POWER_PROCESSED_DIR / f"clima_municipal_{inicio}_{fin}.csv"
        resultado.to_csv(destino, index=False)
        LOGGER.info("Guardado: %s", destino)
    return resultado
