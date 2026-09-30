from pathlib import Path

import pandas as pd
import typer
from loguru import logger
from tqdm import tqdm
import geopandas as gpd

from proyecto_agronomia.config import (
    AGRICULTURA_RAW_DIR,
    ANIOS,
    INTERIM_DATA_DIR,
    PROCESSED_DATA_DIR,
    INEGI_INTERIM_DIR
)

app = typer.Typer()


# Columnas numéricas principales de los datos agrícolas
COLUMNAS_NUMERICAS = [
    "Sembrada",
    "Cosechada",
    "Siniestrada",
    "Volumenproduccion",
    "Rendimiento",
    "Preciomediorural",
    "Valorproduccion",
]


def normalizar_columnas_agricolas(df: pd.DataFrame, anio: int) -> pd.DataFrame:
    """
    Homogeneiza los cambios de nombres de columnas presentes en los
    archivos agrícolas históricos.

    Cambios conocidos:
    - 2003-2014: Nomcultivo + Precio
    - 2015-2020: Nomcultivo Sin Um + Precio
    - 2021-2025: Nomcultivo + Preciomediorural
    """

    df = df.copy()

    # 2015-2020
    if "Nomcultivo Sin Um" in df.columns:
        df = df.rename(
            columns={
                "Nomcultivo Sin Um": "Nomcultivo",
            }
        )

    # 2003-2020
    if "Precio" in df.columns:
        df = df.rename(
            columns={
                "Precio": "Preciomediorural",
            }
        )

    logger.debug(f"[{anio}] Columnas normalizadas.")

    return df


def convertir_columnas_numericas(
    df: pd.DataFrame,
    anio: int,
) -> pd.DataFrame:
    """
    Convierte las variables agrícolas cuantitativas a formato numérico.

    Algunos archivos históricos pueden almacenar números como texto y
    contener separadores de miles.
    """

    df = df.copy()

    for columna in COLUMNAS_NUMERICAS:
        if columna not in df.columns:
            logger.warning(
                f"[{anio}] No se encontró la columna '{columna}'."
            )
            continue

        df[columna] = (
            df[columna]
            .astype(str)
            .str.replace(",", "", regex=False)
        )

        df[columna] = pd.to_numeric(
            df[columna],
            errors="coerce",
        )

    return df


def cargar_archivo_agricola(ruta: Path, anio: int) -> pd.DataFrame:
    """
    Lee y normaliza un archivo agrícola anual.
    """

    df = pd.read_csv(
        ruta,
        encoding="latin-1",
        low_memory=False,
    )

    df = normalizar_columnas_agricolas(df, anio)
    df = convertir_columnas_numericas(df, anio)

    return df


def construir_historico_agricola(
    anios: list[int] = ANIOS,
    directorio: Path = AGRICULTURA_RAW_DIR,
) -> pd.DataFrame:
    """
    Carga y concatena los archivos agrícolas del periodo de estudio.
    """

    dataframes = []

    for anio in tqdm(anios, desc="Procesando datos agrícolas"):
        ruta = directorio / f"agricola_{anio}.csv"

        if not ruta.exists():
            logger.warning(
                f"[{anio}] No existe {ruta.name}. Se omitirá."
            )
            continue

        try:
            df_anio = cargar_archivo_agricola(ruta, anio)

        except Exception as error:
            logger.error(
                f"[{anio}] Error procesando {ruta.name}: {error}"
            )
            continue

        dataframes.append(df_anio)

        logger.info(
            f"[{anio}] {len(df_anio):,} registros procesados."
        )

    if not dataframes:
        raise FileNotFoundError(
            "No se encontraron archivos agrícolas para procesar."
        )

    historico = pd.concat(
        dataframes,
        ignore_index=True,
    )

    return historico

def generar_features_agricolas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Genera variables derivadas para el análisis agrícola.

    TasaCosecha:
        proporción de la superficie sembrada que fue cosechada.

        Cosechada / Sembrada

    Cuando Sembrada es igual a cero, la tasa se mantiene como NA
    para evitar divisiones indefinidas.

    No se eliminan ni corrigen automáticamente observaciones
    inconsistentes; estas se identifican mediante indicadores.
    """

    df = df.copy()

    # Tasa de superficie cosechada
    df["TasaCosecha"] = pd.NA

    mascara_valida = df["Sembrada"] > 0

    df.loc[mascara_valida, "TasaCosecha"] = (
        df.loc[mascara_valida, "Cosechada"]
        / df.loc[mascara_valida, "Sembrada"]
    )

    df["TasaCosecha"] = pd.to_numeric(
        df["TasaCosecha"],
        errors="coerce",
    )

    # Indicadores de calidad de datos
    df["FlagSembradaCero"] = df["Sembrada"] == 0

    df["FlagCosechadaMayorSembrada"] = (
        df["Cosechada"] > df["Sembrada"]
    )

    df["FlagBalanceSuperficie"] = (
        df["Cosechada"] + df["Siniestrada"]
        > df["Sembrada"]
    )

    return df

def generar_coordenadas_municipios(
    municipios_geo: gpd.GeoDataFrame,
) -> pd.DataFrame:
    """
    Genera un punto representativo dentro de cada municipio de INEGI.

    Las geometrías se proyectan a EPSG:6372 antes de realizar la
    operación espacial. Posteriormente, los puntos se transforman
    nuevamente a WGS84 (EPSG:4326) para obtener longitud y latitud.
    """

    municipios_geo = municipios_geo.copy()

    # Proyectar geometrías para realizar operaciones espaciales
    municipios_proyectados = municipios_geo.to_crs(
        epsg=6372
    )

    # Obtener un punto garantizado dentro de cada municipio
    puntos_representativos = (
        municipios_proyectados
        .geometry
        .representative_point()
    )

    # Regresar los puntos a coordenadas geográficas WGS84
    puntos_geo = gpd.GeoSeries(
        puntos_representativos,
        crs=municipios_proyectados.crs,
    ).to_crs(epsg=4326)

    # Crear coordenadas
    municipios_geo["Longitud"] = puntos_geo.x
    municipios_geo["Latitud"] = puntos_geo.y

        # Crear dataset tabular compatible con las claves agrícolas
    municipios_coordenadas = municipios_geo[
        [
            "cve_ent",
            "cve_mun",
            "cvegeo",
            "nomgeo",
            "Latitud",
            "Longitud",
        ]
    ].copy()

    municipios_coordenadas = municipios_coordenadas.rename(
        columns={
            "cve_ent": "Idestado",
            "cve_mun": "Idmunicipio",
            "nomgeo": "Nommunicipio",
        }
    )

    # Las claves agrícolas utilizan valores enteros
    municipios_coordenadas["Idestado"] = (
        municipios_coordenadas["Idestado"].astype(int)
    )

    municipios_coordenadas["Idmunicipio"] = (
        municipios_coordenadas["Idmunicipio"].astype(int)
    )

    return municipios_coordenadas

def guardar_coordenadas_municipios(
    municipios_geo: gpd.GeoDataFrame,
    output_path: Path = (
        INEGI_INTERIM_DIR / "municipios_coordenadas_inegi.csv"
    ),
) -> pd.DataFrame:
    """
    Genera, valida y guarda las coordenadas representativas
    de los municipios de INEGI.
    """

    coordenadas = generar_coordenadas_municipios(
        municipios_geo
    )

    duplicados = coordenadas.duplicated(
        subset=["Idestado", "Idmunicipio"]
    ).sum()

    latitudes_faltantes = (
        coordenadas["Latitud"].isna().sum()
    )

    longitudes_faltantes = (
        coordenadas["Longitud"].isna().sum()
    )

    logger.info(
        f"Municipios: {len(coordenadas):,}"
    )
    logger.info(
        f"Claves duplicadas: {duplicados:,}"
    )
    logger.info(
        f"Latitudes faltantes: {latitudes_faltantes:,}"
    )
    logger.info(
        f"Longitudes faltantes: {longitudes_faltantes:,}"
    )

    logger.info(
        f"Rango latitud: "
        f"{coordenadas['Latitud'].min():.6f} → "
        f"{coordenadas['Latitud'].max():.6f}"
    )

    logger.info(
        f"Rango longitud: "
        f"{coordenadas['Longitud'].min():.6f} → "
        f"{coordenadas['Longitud'].max():.6f}"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    coordenadas.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    logger.success(
        f"Coordenadas municipales guardadas en {output_path}"
    )

    return coordenadas

def obtener_municipios_agricolas(
    anios: list[int] = ANIOS,
    directorio: Path = AGRICULTURA_RAW_DIR,
) -> pd.DataFrame:
    """
    Obtiene los municipios únicos que presentan actividad agrícola
    durante el periodo de estudio.
    """

    municipios_agricolas = []

    for anio in anios:
        archivo = directorio / f"agricola_{anio}.csv"

        if not archivo.exists():
            logger.warning(
                f"No se encontró el archivo agrícola de {anio}: {archivo}"
            )
            continue

        df_temp = pd.read_csv(
            archivo,
            encoding="latin-1",
            low_memory=False,
            usecols=[
                "Idestado",
                "Idmunicipio",
                "Nommunicipio",
            ],
        )

        municipios_agricolas.append(
            df_temp[
                [
                    "Idestado",
                    "Idmunicipio",
                    "Nommunicipio",
                ]
            ].drop_duplicates()
        )

    if not municipios_agricolas:
        raise FileNotFoundError(
            "No se encontraron archivos agrícolas para obtener municipios."
        )

    municipios_agricolas = (
        pd.concat(
            municipios_agricolas,
            ignore_index=True,
        )
        .drop_duplicates(
            subset=["Idestado", "Idmunicipio"]
        )
        .reset_index(drop=True)
    )

    logger.info(
        f"Municipios con actividad agrícola: "
        f"{len(municipios_agricolas):,}"
    )

    return municipios_agricolas

def preparar_municipios_clima(
    municipios_agricolas: pd.DataFrame,
    municipios_coordenadas: pd.DataFrame,
) -> pd.DataFrame:
    """
    Integra los municipios con actividad agrícola con las coordenadas
    representativas obtenidas a partir de INEGI.

    La llave de integración es (Idestado, Idmunicipio).
    """

    municipios_clima = municipios_agricolas.merge(
        municipios_coordenadas[
            [
                "Idestado",
                "Idmunicipio",
                "Latitud",
                "Longitud",
            ]
        ],
        on=["Idestado", "Idmunicipio"],
        how="left",
        validate="one_to_one",
    )

    sin_coordenadas = (
        municipios_clima["Latitud"].isna()
        | municipios_clima["Longitud"].isna()
    ).sum()

    logger.info(
        f"Municipios agrícolas: {len(municipios_clima):,}"
    )

    logger.info(
        f"Municipios sin coordenadas: {sin_coordenadas:,}"
    )

    return municipios_clima

def resumir_clima_anual(
    datos: dict,
    municipio: pd.Series,
) -> pd.DataFrame:
    """
    Resume los datos climáticos diarios de un municipio a escala anual.

    El resultado contiene una observación por municipio y año,
    identificada mediante (Anio, Idestado, Idmunicipio).
    """

    df = pd.DataFrame(datos["daily"])

    df["Fecha"] = pd.to_datetime(df["time"])
    df["Anio"] = df["Fecha"].dt.year

    # Día con precipitación registrada
    df["Dia_con_lluvia"] = (
        df["precipitation_sum"] > 0
    ).astype(int)

    resumen = (
        df
        .groupby("Anio", as_index=False)
        .agg(
            Temperatura_media=(
                "temperature_2m_mean",
                "mean",
            ),
            Temperatura_maxima=(
                "temperature_2m_max",
                "max",
            ),
            Temperatura_minima=(
                "temperature_2m_min",
                "min",
            ),
            Precipitacion_anual=(
                "precipitation_sum",
                "sum",
            ),
            Dias_con_lluvia=(
                "Dia_con_lluvia",
                "sum",
            ),
            Horas_precipitacion=(
                "precipitation_hours",
                "sum",
            ),
            Evapotranspiracion_anual=(
                "et0_fao_evapotranspiration",
                "sum",
            ),
        )
    )

    # Identificación geográfica
    resumen["Idestado"] = int(municipio["Idestado"])
    resumen["Idmunicipio"] = int(municipio["Idmunicipio"])
    resumen["Nommunicipio"] = municipio["Nommunicipio"]

    resumen["Latitud"] = municipio["Latitud"]
    resumen["Longitud"] = municipio["Longitud"]

    # Redondear variables climáticas
    columnas_clima = [
        "Temperatura_media",
        "Temperatura_maxima",
        "Temperatura_minima",
        "Precipitacion_anual",
        "Horas_precipitacion",
        "Evapotranspiracion_anual",
    ]

    resumen[columnas_clima] = (
        resumen[columnas_clima]
        .round(2)
    )

    return resumen

def resumir_clima_lote(
    datos_lote: list[dict],
    municipios: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convierte las respuestas diarias de Open-Meteo de un lote
    de municipios en observaciones climáticas anuales.
    """

    if len(datos_lote) != len(municipios):
        raise ValueError(
            "El número de respuestas climáticas no coincide "
            "con el número de municipios."
        )

    resumenes = []

    for i, datos in enumerate(datos_lote):
        municipio = municipios.iloc[i]

        resumen = resumir_clima_anual(
            datos,
            municipio,
        )

        resumenes.append(resumen)

    if not resumenes:
        return pd.DataFrame()

    return pd.concat(
        resumenes,
        ignore_index=True,
    )

@app.command()
def main(
    input_path: Path = INTERIM_DATA_DIR / "agricultura_historica.csv",
    output_path: Path = PROCESSED_DATA_DIR / "agricultura_features.csv",
):
    """
    Genera el dataset agrícola procesado con variables derivadas.
    """

    logger.info(f"Leyendo dataset histórico desde {input_path}")

    if not input_path.exists():
        raise FileNotFoundError(
            f"No se encontró el dataset histórico: {input_path}"
        )

    df = pd.read_csv(
        input_path,
        low_memory=False,
    )

    logger.info(
        f"Dataset cargado: {df.shape[0]:,} filas x "
        f"{df.shape[1]} columnas."
    )

    df = generar_features_agricolas(df)

    logger.info(
        f"Features generadas: {df.shape[0]:,} filas x "
        f"{df.shape[1]} columnas."
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        output_path,
        index=False,
        encoding="utf-8",
    )

    logger.success(
        f"Dataset procesado guardado en {output_path}"
    )

if __name__ == "__main__":
    app()