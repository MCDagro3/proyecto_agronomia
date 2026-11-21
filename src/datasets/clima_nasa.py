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

PERIODOS_AGRICOLAS = {
    "Otoño-Invierno": ((-1, 10, 1), (0, 3, 31)),
    "Primavera-Verano": ((0, 4, 1), (0, 9, 30)),
    "Perennes": ((0, 1, 1), (0, 12, 31)),
}

TRIMESTRES = {
    "T1": (1, 3),
    "T2": (4, 6),
    "T3": (7, 9),
    "T4": (10, 12),
}

MESES = tuple(range(1, 13))


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


def resumir_nasa_power_por_periodos(
    datos: dict,
    cvegeo: str,
    inicio: int = NASA_POWER_ANIO_INICIAL,
    fin: int = NASA_POWER_ANIO_FINAL,
) -> pd.DataFrame:
    """Agrega datos diarios a los periodos agrícolas usados por SIAP.

    ``Otoño-Invierno`` del año ``n`` abarca octubre-diciembre de ``n-1`` y
    enero-marzo de ``n``. ``Primavera-Verano`` comprende abril-septiembre y
    ``Perennes`` conserva el año calendario completo.
    """
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
        for periodo, (inicio_relativo, fin_relativo) in PERIODOS_AGRICOLAS.items():
            fecha_inicio = pd.Timestamp(
                year=anio + inicio_relativo[0],
                month=inicio_relativo[1],
                day=inicio_relativo[2],
            )
            fecha_fin = pd.Timestamp(
                year=anio + fin_relativo[0],
                month=fin_relativo[1],
                day=fin_relativo[2],
            )
            dias = diario.loc[fecha_inicio:fecha_fin]
            dias_esperados = int((fecha_fin - fecha_inicio).days + 1)
            temperatura = dias["T2M"]
            precipitacion = dias["PRECTOTCORR"]
            completo_temperatura = (
                len(dias) == dias_esperados
                and temperatura.notna().sum() == dias_esperados
            )
            completo_precipitacion = (
                len(dias) == dias_esperados
                and precipitacion.notna().sum() == dias_esperados
            )
            filas.append(
                {
                    "cvegeo": str(cvegeo).zfill(5),
                    "anio": anio,
                    "periodo_climatico": periodo,
                    "fecha_inicio": fecha_inicio.date().isoformat(),
                    "fecha_fin": fecha_fin.date().isoformat(),
                    "temperatura_media_periodo_c": (
                        float(temperatura.mean()) if completo_temperatura else np.nan
                    ),
                    "precipitacion_periodo_mm": (
                        float(precipitacion.sum()) if completo_precipitacion else np.nan
                    ),
                    "dias_esperados": dias_esperados,
                    "dias_temperatura": int(temperatura.notna().sum()),
                    "dias_precipitacion": int(precipitacion.notna().sum()),
                    "fuente": "NASA POWER",
                }
            )
    return pd.DataFrame(filas)


def resumir_nasa_power_trimestral(
    datos: dict,
    cvegeo: str,
    inicio: int,
    fin: int,
) -> pd.DataFrame:
    """Agrega temperatura y precipitación diaria por trimestre calendario."""
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
        for trimestre, (mes_inicial, mes_final) in TRIMESTRES.items():
            fecha_inicio = pd.Timestamp(year=anio, month=mes_inicial, day=1)
            fecha_fin = pd.Timestamp(year=anio, month=mes_final, day=1) + pd.offsets.MonthEnd(0)
            dias = diario.loc[fecha_inicio:fecha_fin]
            dias_esperados = int((fecha_fin - fecha_inicio).days + 1)
            temperatura = dias["T2M"]
            precipitacion = dias["PRECTOTCORR"]
            completo_temperatura = (
                len(dias) == dias_esperados
                and temperatura.notna().sum() == dias_esperados
            )
            completo_precipitacion = (
                len(dias) == dias_esperados
                and precipitacion.notna().sum() == dias_esperados
            )
            filas.append(
                {
                    "cvegeo": str(cvegeo).zfill(5),
                    "anio": anio,
                    "trimestre": trimestre,
                    "fecha_inicio": fecha_inicio.date().isoformat(),
                    "fecha_fin": fecha_fin.date().isoformat(),
                    "temperatura_media_trimestre_c": (
                        float(temperatura.mean()) if completo_temperatura else np.nan
                    ),
                    "precipitacion_trimestre_mm": (
                        float(precipitacion.sum()) if completo_precipitacion else np.nan
                    ),
                    "dias_esperados": dias_esperados,
                    "dias_temperatura": int(temperatura.notna().sum()),
                    "dias_precipitacion": int(precipitacion.notna().sum()),
                    "fuente": "NASA POWER",
                }
            )
    return pd.DataFrame(filas)


def resumir_nasa_power_mensual(
    datos: dict,
    cvegeo: str,
    inicio: int,
    fin: int,
) -> pd.DataFrame:
    """Agrega temperatura media y precipitación acumulada por mes calendario."""
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
        for mes in MESES:
            fecha_inicio = pd.Timestamp(year=anio, month=mes, day=1)
            fecha_fin = fecha_inicio + pd.offsets.MonthEnd(0)
            dias = diario.loc[fecha_inicio:fecha_fin]
            dias_esperados = int(fecha_fin.day)
            temperatura = dias["T2M"]
            precipitacion = dias["PRECTOTCORR"]
            completo_temperatura = (
                len(dias) == dias_esperados
                and temperatura.notna().sum() == dias_esperados
            )
            completo_precipitacion = (
                len(dias) == dias_esperados
                and precipitacion.notna().sum() == dias_esperados
            )
            filas.append(
                {
                    "cvegeo": str(cvegeo).zfill(5),
                    "anio": anio,
                    "mes": mes,
                    "fecha_inicio": fecha_inicio.date().isoformat(),
                    "fecha_fin": fecha_fin.date().isoformat(),
                    "temperatura_media_mes_c": (
                        float(temperatura.mean()) if completo_temperatura else np.nan
                    ),
                    "precipitacion_mes_mm": (
                        float(precipitacion.sum()) if completo_precipitacion else np.nan
                    ),
                    "dias_esperados": dias_esperados,
                    "dias_temperatura": int(temperatura.notna().sum()),
                    "dias_precipitacion": int(precipitacion.notna().sum()),
                    "fuente": "NASA POWER",
                }
            )
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


def descargar_clima_nasa_periodos_por_celdas(
    municipios: pd.DataFrame,
    inicio: int = NASA_POWER_ANIO_INICIAL,
    fin: int = NASA_POWER_ANIO_FINAL,
    pausa: float = NASA_POWER_PAUSA,
    resolucion_latitud: float = 0.5,
    resolucion_longitud: float = 0.625,
    frecuencia: str = "periodos",
) -> pd.DataFrame:
    """Descarga y agrega NASA POWER por municipio, año y periodo agrícola.

    Reutiliza los JSON por celda de 2003-2022 y los JSON municipales de
    2023-2025. Solo consulta 2002 por celda para completar el primer periodo
    Otoño-Invierno. Todo archivo nuevo se conserva para poder reanudar.
    """
    import json

    if frecuencia not in {"periodos", "trimestres", "meses"}:
        raise ValueError("frecuencia debe ser 'periodos', 'trimestres' o 'meses'")

    requeridas = {"cvegeo", "Latitud", "Longitud"}
    faltantes = requeridas - set(municipios.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas: {sorted(faltantes)}")
    if inicio > fin:
        raise ValueError("El año inicial no puede ser mayor que el año final")
    if pausa < 0:
        raise ValueError("La pausa no puede ser negativa")

    base = municipios.copy()
    base["cvegeo"] = base["cvegeo"].astype("string").str.zfill(5)
    base = base.drop_duplicates("cvegeo").copy()
    base[["Latitud", "Longitud"]] = base[["Latitud", "Longitud"]].apply(
        pd.to_numeric,
        errors="coerce",
    )
    if base[["Latitud", "Longitud"]].isna().any().any():
        raise ValueError("Hay coordenadas municipales faltantes o no válidas")

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
        "NASA POWER por periodos %s-%s: %s municipios en %s celdas",
        inicio,
        fin,
        len(base),
        len(grupos),
    )
    with requests.Session() as sesion:
        for numero, ((indice_lat, indice_lon), grupo) in enumerate(grupos, 1):
            celda_lat = float(grupo["celda_lat"].iloc[0])
            celda_lon = float(grupo["celda_lon"].iloc[0])
            archivo_2002 = NASA_POWER_RAW_DIR / (
                f"nasa_celda_lat{indice_lat}_lon{indice_lon}_{inicio - 1}_{inicio - 1}.json"
            )
            archivo_historico = NASA_POWER_RAW_DIR / (
                f"nasa_celda_lat{indice_lat}_lon{indice_lon}_{inicio}_2022.json"
            )

            if archivo_2002.exists():
                with archivo_2002.open("r", encoding="utf-8") as f:
                    datos_2002 = json.load(f)
            else:
                datos_2002 = consultar_nasa_power(
                    celda_lat,
                    celda_lon,
                    inicio - 1,
                    inicio - 1,
                    sesion,
                )
                temporal = archivo_2002.with_suffix(".tmp")
                with temporal.open("w", encoding="utf-8") as f:
                    json.dump(datos_2002, f)
                temporal.replace(archivo_2002)
                time.sleep(pausa)

            if archivo_historico.exists():
                with archivo_historico.open("r", encoding="utf-8") as f:
                    datos_historicos = json.load(f)
            else:
                datos_historicos = consultar_nasa_power(
                    celda_lat,
                    celda_lon,
                    inicio,
                    2022,
                    sesion,
                )
                temporal = archivo_historico.with_suffix(".tmp")
                with temporal.open("w", encoding="utf-8") as f:
                    json.dump(datos_historicos, f)
                temporal.replace(archivo_historico)
                time.sleep(pausa)

            for fila in grupo.itertuples(index=False):
                archivo_reciente = NASA_POWER_RAW_DIR / (
                    f"nasa_{fila.cvegeo}_2023_{fin}.json"
                )
                if archivo_reciente.exists():
                    with archivo_reciente.open("r", encoding="utf-8") as f:
                        datos_recientes = json.load(f)
                else:
                    datos_recientes = consultar_nasa_power(
                        float(fila.Latitud),
                        float(fila.Longitud),
                        2023,
                        fin,
                        sesion,
                    )
                    temporal = archivo_reciente.with_suffix(".tmp")
                    with temporal.open("w", encoding="utf-8") as f:
                        json.dump(datos_recientes, f)
                    temporal.replace(archivo_reciente)
                    time.sleep(pausa)

                parametros_combinados = {}
                for variable in PARAMETROS:
                    parametros_combinados[variable] = {}
                    for fragmento in (datos_2002, datos_historicos, datos_recientes):
                        parametros_combinados[variable].update(
                            fragmento["properties"]["parameter"][variable]
                        )
                datos_combinados = {
                    "properties": {"parameter": parametros_combinados}
                }
                if frecuencia == "periodos":
                    tabla = resumir_nasa_power_por_periodos(
                        datos_combinados,
                        fila.cvegeo,
                        inicio,
                        fin,
                    )
                elif frecuencia == "trimestres":
                    tabla = resumir_nasa_power_trimestral(
                        datos_combinados,
                        fila.cvegeo,
                        inicio - 1,
                        fin,
                    )
                else:
                    tabla = resumir_nasa_power_mensual(
                        datos_combinados,
                        fila.cvegeo,
                        inicio - 1,
                        fin,
                    )
                tabla["celda_lat"] = celda_lat
                tabla["celda_lon"] = celda_lon
                tablas.append(tabla)

            if numero % 25 == 0 or numero == len(grupos):
                LOGGER.info("Procesadas %s/%s celdas", numero, len(grupos))

    resultado = pd.concat(tablas, ignore_index=True) if tablas else pd.DataFrame()
    if not resultado.empty:
        dimensiones = {
            "periodos": "periodo_climatico",
            "trimestres": "trimestre",
            "meses": "mes",
        }
        dimension_temporal = dimensiones[frecuencia]
        claves = ["cvegeo", "anio", dimension_temporal]
        resultado = resultado.sort_values(claves).reset_index(drop=True)
        if resultado.duplicated(claves).any():
            raise ValueError("La descarga generó claves municipio-año-periodo duplicadas")
        if frecuencia == "periodos":
            destino = NASA_POWER_PROCESSED_DIR / (
                f"clima_municipal_periodos_{inicio}_{fin}.csv"
            )
        elif frecuencia == "trimestres":
            destino = NASA_POWER_PROCESSED_DIR / (
                f"clima_municipal_trimestral_{inicio - 1}_{fin}.csv"
            )
        else:
            destino = NASA_POWER_PROCESSED_DIR / (
                f"clima_municipal_mensual_{inicio - 1}_{fin}.csv"
            )
        resultado.to_csv(destino, index=False)
        LOGGER.info("Guardado: %s", destino)
    return resultado


def descargar_clima_nasa_mensual_por_celdas(
    municipios: pd.DataFrame,
    inicio: int = NASA_POWER_ANIO_INICIAL,
    fin: int = NASA_POWER_ANIO_FINAL,
    pausa: float = NASA_POWER_PAUSA,
) -> pd.DataFrame:
    """Genera el dataset climático mensual reutilizando los JSON diarios."""
    return descargar_clima_nasa_periodos_por_celdas(
        municipios=municipios,
        inicio=inicio,
        fin=fin,
        pausa=pausa,
        frecuencia="meses",
    )
