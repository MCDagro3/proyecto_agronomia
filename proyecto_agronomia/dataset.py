from pathlib import Path

import requests
import typer
from loguru import logger
from tqdm import tqdm
import geopandas as gpd
import pandas as pd
import time

from proyecto_agronomia.features import resumir_clima_lote
from proyecto_agronomia.config import (
    AGRICULTURA_RAW_DIR,
    AGRICULTURA_URL_TEMPLATE,
    ANIOS,
    CLIMA_RAW_DIR,
    ESTADOS,
    INEGI_ESTADOS_URL_TEMPLATE,
    INEGI_INTERIM_DIR,
    INEGI_MUNICIPIOS_URL_TEMPLATE,
    OPEN_METEO_ARCHIVE_URL,
    AGRICULTURA_DICCIONARIO_PATH,
    AGRICULTURA_DICCIONARIO_URL,
)

app = typer.Typer()


def descargar_datos_agricolas(
    anios: list[int],
    directorio: Path = AGRICULTURA_RAW_DIR,
) -> list[Path]:
    """
    Descarga los archivos agrícolas anuales de la Secretaría de Agricultura.

    Los archivos se guardan en data/raw/agricultura. Si un archivo ya existe,
    no se vuelve a descargar.

    Parameters
    ----------
    anios : list[int]
        Años que se desean descargar.
    directorio : Path
        Directorio donde se almacenarán los archivos CSV.

    Returns
    -------
    list[Path]
        Rutas de los archivos disponibles después de la descarga.
    """

    directorio.mkdir(parents=True, exist_ok=True)

    archivos = []

    for anio in tqdm(anios, desc="Datos agrícolas"):
        url = AGRICULTURA_URL_TEMPLATE.format(anio=anio)
        ruta = directorio / f"agricola_{anio}.csv"

        if ruta.exists():
            logger.info(f"[{anio}] El archivo ya existe.")
            archivos.append(ruta)
            continue

        logger.info(f"[{anio}] Descargando...")

        try:
            respuesta = requests.get(url, timeout=120)
            respuesta.raise_for_status()

            ruta.write_bytes(respuesta.content)

        except requests.RequestException as error:
            logger.error(f"[{anio}] Error durante la descarga: {error}")
            continue

        logger.success(
            f"[{anio}] Descargado "
            f"({ruta.stat().st_size / (1024**2):.2f} MB)"
        )

        archivos.append(ruta)

    return archivos

def descargar_diccionario_agricola(
    ruta: Path = AGRICULTURA_DICCIONARIO_PATH,
) -> Path:
    """
    Descarga el diccionario oficial de los datos de Cierre de la
    Producción Agrícola de la DGSIAP.

    El archivo se almacena en references/ como documentación de la
    fuente de datos. Si el archivo ya existe, no se vuelve a descargar.

    Parameters
    ----------
    ruta : Path
        Ruta donde se almacenará el diccionario XLSX.

    Returns
    -------
    Path
        Ruta del diccionario disponible localmente.
    """

    ruta.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if ruta.exists():
        logger.info(
            "El diccionario agrícola ya existe."
        )
        return ruta

    logger.info(
        "Descargando diccionario agrícola DGSIAP..."
    )

    try:
        respuesta = requests.get(
            AGRICULTURA_DICCIONARIO_URL,
            timeout=120,
        )

        respuesta.raise_for_status()

        ruta.write_bytes(
            respuesta.content
        )

    except requests.RequestException as error:
        logger.error(
            "Error descargando el diccionario "
            f"agrícola: {error}"
        )
        raise

    logger.success(
        "Diccionario agrícola descargado: "
        f"{ruta.name}"
    )

    return ruta

def obtener_municipios_inegi(
    directorio: Path = INEGI_INTERIM_DIR,
) -> gpd.GeoDataFrame:
    """
    Descarga las geometrías municipales de México desde INEGI.

    Si el archivo local ya existe, se reutiliza para evitar
    descargar nuevamente la información.
    """

    directorio.mkdir(parents=True, exist_ok=True)

    ruta_geojson = directorio / "municipios_mexico_inegi.geojson"

    if ruta_geojson.exists():
        logger.info("Cargando municipios INEGI desde archivo local.")

        return gpd.read_file(ruta_geojson)

    features = []

    for id_estado in tqdm(
        range(1, 33),
        desc="Municipios INEGI",
    ):
        clave_estado = f"{id_estado:02d}"

        url = INEGI_MUNICIPIOS_URL_TEMPLATE.format(
            clave_estado=clave_estado
        )

        logger.info(
            f"Descargando municipios del estado {clave_estado}."
        )

        try:
            respuesta = requests.get(
                url,
                timeout=120,
            )

            respuesta.raise_for_status()
            datos = respuesta.json()

        except requests.RequestException as error:
            logger.error(
                f"Error descargando estado {clave_estado}: {error}"
            )
            raise

        features.extend(
            datos["features"]
        )

    municipios_geo = gpd.GeoDataFrame.from_features(
        features,
        crs="EPSG:4326",
    )

    municipios_geo.to_file(
        ruta_geojson,
        driver="GeoJSON",
    )

    logger.success(
        f"Municipios INEGI guardados: {len(municipios_geo):,}"
    )

    return municipios_geo

def obtener_estados_inegi(
    directorio: Path = INEGI_INTERIM_DIR,
) -> gpd.GeoDataFrame:
    """
    Descarga las geometrías de las 32 entidades federativas desde INEGI.

    Si el archivo local ya existe, se reutiliza para evitar
    descargar nuevamente la información.
    """

    directorio.mkdir(parents=True, exist_ok=True)

    ruta_geojson = directorio / "estados_mexico_inegi.geojson"

    if ruta_geojson.exists():
        logger.info("Cargando estados INEGI desde archivo local.")
        return gpd.read_file(ruta_geojson)

    features = []

    for id_estado in tqdm(
        range(1, 33),
        desc="Estados INEGI",
    ):
        clave_estado = f"{id_estado:02d}"

        url = INEGI_ESTADOS_URL_TEMPLATE.format(
            clave_estado=clave_estado
        )

        logger.info(
            f"Descargando estado {clave_estado}."
        )

        try:
            respuesta = requests.get(
                url,
                timeout=60,
            )
            respuesta.raise_for_status()
            datos = respuesta.json()

        except requests.RequestException as error:
            logger.error(
                f"Error descargando estado {clave_estado}: {error}"
            )
            raise

        features.extend(datos["features"])

    estados_geo = gpd.GeoDataFrame.from_features(
        features,
        crs="EPSG:4326",
    )

    estados_geo.to_file(
        ruta_geojson,
        driver="GeoJSON",
    )

    logger.success(
        f"Entidades geográficas guardadas: {len(estados_geo)}"
    )

    return estados_geo

def obtener_clima_lote(
    municipios: pd.DataFrame,
    anio_inicio: int = 2003,
    anio_fin: int = 2025,
):
    """
    Consulta datos climáticos históricos diarios de Open-Meteo
    para un lote de municipios.
    """

    latitudes = municipios["Latitud"].tolist()
    longitudes = municipios["Longitud"].tolist()

    parametros = {
        "latitude": ",".join(map(str, latitudes)),
        "longitude": ",".join(map(str, longitudes)),
        "start_date": f"{anio_inicio}-01-01",
        "end_date": f"{anio_fin}-12-31",
        "daily": ",".join(
            [
                "temperature_2m_mean",
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_sum",
                "precipitation_hours",
                "et0_fao_evapotranspiration",
            ]
        ),
        "timezone": "auto",
        "models": "era5",
    }

    respuesta = requests.get(
        OPEN_METEO_ARCHIVE_URL,
        params=parametros,
        timeout=180,
    )

    respuesta.raise_for_status()

    return respuesta.json()

def descargar_clima_estado(
    id_estado: int,
    municipios_clima: pd.DataFrame,
    tamano_lote: int = 2,
    anio_inicio: int = 2003,
    anio_fin: int = 2025,
    pausa: int = 10,
    max_reintentos: int = 4,
) -> pd.DataFrame:
    """
    Descarga y resume los datos climáticos de los municipios agrícolas
    de una entidad federativa.

    El progreso se guarda después de cada lote, permitiendo reanudar
    una descarga interrumpida.
    """

    nombre_estado = ESTADOS[id_estado]

    CLIMA_RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    archivo_estado = (
        CLIMA_RAW_DIR
        / f"clima_{id_estado:02d}_{nombre_estado}.csv"
    )

    municipios_estado = (
        municipios_clima[
            municipios_clima["Idestado"] == id_estado
        ]
        .copy()
        .reset_index(drop=True)
    )

    anios_esperados = anio_fin - anio_inicio + 1

    logger.info(
        f"Estado: {nombre_estado} | "
        f"Municipios agrícolas: {len(municipios_estado):,}"
    )

    # Recuperar progreso existente
    if archivo_estado.exists():
        clima_guardado = pd.read_csv(
            archivo_estado
        )

        conteo = (
            clima_guardado
            .groupby(
                ["Idestado", "Idmunicipio"]
            )["Anio"]
            .nunique()
        )

        municipios_completos = {
            (int(id_estado_), int(id_municipio))
            for (
                id_estado_,
                id_municipio,
            ), n_anios in conteo.items()
            if n_anios == anios_esperados
        }

        logger.info(
            f"Municipios ya descargados: "
            f"{len(municipios_completos):,}"
        )

    else:
        clima_guardado = pd.DataFrame()
        municipios_completos = set()

        logger.info(
            "No existe archivo climático previo para el estado."
        )

    # Encontrar municipios pendientes
    pendientes = municipios_estado[
        ~municipios_estado.apply(
            lambda fila: (
                int(fila["Idestado"]),
                int(fila["Idmunicipio"]),
            ) in municipios_completos,
            axis=1,
        )
    ].copy()

    pendientes = pendientes.reset_index(
        drop=True
    )

    logger.info(
        f"Municipios pendientes: {len(pendientes):,}"
    )

    if pendientes.empty:
        logger.success(
            f"{nombre_estado}: estado completo. "
            "No se requieren solicitudes."
        )
        return clima_guardado

    total_lotes = (
        len(pendientes) + tamano_lote - 1
    ) // tamano_lote

    for numero_lote, inicio in enumerate(
        range(
            0,
            len(pendientes),
            tamano_lote,
        ),
        start=1,
    ):
        lote = (
            pendientes
            .iloc[
                inicio:
                inicio + tamano_lote
            ]
            .copy()
            .reset_index(drop=True)
        )

        logger.info(
            f"{nombre_estado}: lote "
            f"{numero_lote}/{total_lotes} "
            f"({len(lote)} municipios)"
        )

        datos_lote = None

        # Reintentos
        for intento in range(
            1,
            max_reintentos + 1,
        ):
            try:
                datos_lote = obtener_clima_lote(
                    lote,
                    anio_inicio,
                    anio_fin,
                )

                logger.success(
                    "Solicitud climática exitosa."
                )
                break

            except requests.HTTPError as error:
                status = (
                    error.response.status_code
                    if error.response is not None
                    else None
                )

                if status == 429:
                    esperas_429 = [60, 120, 300, 600, 900, 1800]
                    espera = esperas_429[
                        min(intento - 1, len(esperas_429) - 1)
                    ]

                    logger.warning(
                        f"429 Too Many Requests. "
                        f"Esperando {espera} segundos."
                    )

                    time.sleep(espera)

                else:
                    logger.error(
                        f"HTTP {status}: {error}"
                    )
                    raise

            except requests.RequestException as error:
                espera = 15 * intento

                logger.warning(
                    f"Error de conexión: {error}. "
                    f"Esperando {espera} segundos."
                )

                time.sleep(espera)

        if datos_lote is None:
            logger.error(
                "No se pudo descargar el lote después "
                "de los reintentos. El progreso anterior "
                "permanece guardado."
            )
            raise RuntimeError(
                f"Descarga detenida por límite de solicitudes "
                f"en {nombre_estado}. Reanudar más tarde."
            )
        if not isinstance(datos_lote, list):
            datos_lote = [datos_lote]

        clima_lote = resumir_clima_lote(
            datos_lote,
            lote,
        )

        # Guardar inmediatamente
        if clima_guardado.empty:
            clima_guardado = clima_lote.copy()
        else:
            clima_guardado = pd.concat(
                [
                    clima_guardado,
                    clima_lote,
                ],
                ignore_index=True,
            )

        clima_guardado = (
            clima_guardado
            .drop_duplicates(
                subset=[
                    "Idestado",
                    "Idmunicipio",
                    "Anio",
                ],
                keep="last",
            )
            .sort_values(
                [
                    "Idestado",
                    "Idmunicipio",
                    "Anio",
                ]
            )
            .reset_index(drop=True)
        )

        clima_guardado.to_csv(
            archivo_estado,
            index=False,
            encoding="utf-8-sig",
        )

        completados = (
            clima_guardado
            .groupby(
                ["Idestado", "Idmunicipio"]
            )["Anio"]
            .nunique()
            .eq(anios_esperados)
            .sum()
        )

        logger.info(
            f"Guardado: {completados}/"
            f"{len(municipios_estado)} municipios."
        )

        time.sleep(pausa)

    completos_finales = (
        clima_guardado
        .groupby(
            ["Idestado", "Idmunicipio"]
        )["Anio"]
        .nunique()
        .eq(anios_esperados)
        .sum()
    )

    if completos_finales == len(municipios_estado):
        logger.success(
            f"{nombre_estado.upper()} COMPLETO."
        )
    else:
        logger.warning(
            f"{nombre_estado}: "
            f"{completos_finales}/"
            f"{len(municipios_estado)} municipios completos."
        )

    logger.info(
        f"Archivo: {archivo_estado.name} | "
        f"Filas: {len(clima_guardado):,}"
    )

    return clima_guardado

def descargar_clima_todos_estados(
    municipios_clima: pd.DataFrame,
    tamano_lote: int = 2,
    anio_inicio: int = 2003,
    anio_fin: int = 2025,
    pausa: int = 10,
) -> pd.DataFrame:
    """
    Descarga los datos climáticos de todos los estados de México.

    Cada estado se procesa de manera independiente y conserva su
    progreso en data/raw/clima, permitiendo reanudar la descarga
    si el proceso se interrumpe.
    """

    resumen_estados = []

    logger.info(
        f"Descarga climática nacional | "
        f"Periodo: {anio_inicio}-{anio_fin} | "
        f"Estados: {len(ESTADOS)} | "
        f"Municipios agrícolas: {len(municipios_clima):,}"
    )

    for id_estado, nombre_estado in ESTADOS.items():

        municipios_estado = (
            municipios_clima[
                municipios_clima["Idestado"] == id_estado
            ]
            .copy()
        )

        total_municipios = len(municipios_estado)

        logger.info(
            f"Procesando estado {id_estado:02d}/32: "
            f"{nombre_estado.upper()} | "
            f"{total_municipios} municipios"
        )

        try:
            clima_estado = descargar_clima_estado(
                id_estado=id_estado,
                municipios_clima=municipios_clima,
                tamano_lote=tamano_lote,
                anio_inicio=anio_inicio,
                anio_fin=anio_fin,
                pausa=pausa,
            )

            if (
                clima_estado is not None
                and not clima_estado.empty
            ):
                anios_esperados = (
                    anio_fin - anio_inicio + 1
                )

                completos = (
                    clima_estado
                    .groupby(
                        ["Idestado", "Idmunicipio"]
                    )["Anio"]
                    .nunique()
                    .eq(anios_esperados)
                    .sum()
                )

            else:
                completos = 0

            estado_completo = (
                completos == total_municipios
            )

            resumen_estados.append(
                {
                    "Idestado": id_estado,
                    "Estado": nombre_estado,
                    "Municipios": total_municipios,
                    "Completos": completos,
                    "Estado_completo": estado_completo,
                }
            )

            if estado_completo:
                logger.success(
                    f"{nombre_estado.upper()} FINALIZADO."
                )
            else:
                logger.warning(
                    f"{nombre_estado.upper()} PARCIAL: "
                    f"{completos}/{total_municipios}"
                )
         
        except RuntimeError as error:
            logger.error(
                f"Descarga detenida en {nombre_estado}: {error}"
            )

            logger.warning(
                "Se detiene la descarga nacional. "
                "El progreso guardado se conserva y "
                "puede reanudarse posteriormente."
            )

            raise

        except Exception as error:
            logger.error(
                f"Error procesando {nombre_estado}: {error}"
            )

            resumen_estados.append(
                {
                    "Idestado": id_estado,
                    "Estado": nombre_estado,
                    "Municipios": total_municipios,
                    "Completos": None,
                    "Estado_completo": False,
                }
            )

            logger.warning(
                "Continuando con el siguiente estado."
            )

        # Descanso adicional entre estados
        time.sleep(15)

    resumen_estados = pd.DataFrame(
        resumen_estados
    )

    estados_completos = (
        resumen_estados["Estado_completo"].sum()
    )

    municipios_completos = (
        resumen_estados["Completos"]
        .fillna(0)
        .sum()
    )

    logger.info(
        f"Resumen nacional | "
        f"Estados completos: {estados_completos}/32 | "
        f"Municipios completos: "
        f"{municipios_completos:,.0f}/"
        f"{len(municipios_clima):,}"
    )

    return resumen_estados

@app.command()
def main():
    """Descarga los datos agrícolas correspondientes al periodo de estudio."""

    logger.info(
        f"Descargando datos agrícolas para {ANIOS[0]}-{ANIOS[-1]}."
    )

    archivos = descargar_datos_agricolas(ANIOS)

    logger.success(
        f"Proceso terminado. {len(archivos)} archivos disponibles."
    )


if __name__ == "__main__":
    app()