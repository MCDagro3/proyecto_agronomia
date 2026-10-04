import time

import pandas as pd
import requests
from loguru import logger

from proyecto_agronomia.config import (
    ANIO_FINAL,
    ANIO_INICIAL,
    CLIMA_RAW_DIR,
    BATCHES_CLIMA,
    ESTADOS,
    OPEN_METEO_ARCHIVE_URL,
)

from proyecto_agronomia.features import (
    resumir_clima_lote,
)


def obtener_clima_lote(
    municipios: pd.DataFrame,
    anio_inicio: int = ANIO_INICIAL,
    anio_fin: int = ANIO_FINAL,
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

def descargar_clima_estados(
    municipios_clima: pd.DataFrame,
    ids_estados: list[int],
    tamano_lote: int = 2,
    anio_inicio: int = ANIO_INICIAL,
    anio_fin: int = ANIO_FINAL,
    pausa: int = 10,
) -> pd.DataFrame:
    """
    Descarga datos climáticos para un conjunto de estados.

    Cada estado conserva su progreso de manera independiente,
    permitiendo reanudar descargas interrumpidas.
    """

    ids_estados = list(ids_estados)

    estados_invalidos = [
        id_estado
        for id_estado in ids_estados
        if id_estado not in ESTADOS
    ]

    if estados_invalidos:
        raise ValueError(
            "Estados no válidos: "
            f"{estados_invalidos}"
        )

    resumen_estados = []

    logger.info(
        f"Descarga climática | "
        f"Periodo: {anio_inicio}-{anio_fin} | "
        f"Estados: {len(ids_estados)}"
    )

    for posicion, id_estado in enumerate(
        ids_estados,
        start=1,
    ):
        nombre_estado = ESTADOS[id_estado]

        municipios_estado = (
            municipios_clima[
                municipios_clima["Idestado"] == id_estado
            ]
            .copy()
        )

        total_municipios = len(
            municipios_estado
        )

        logger.info(
            f"Procesando estado "
            f"{posicion}/{len(ids_estados)} | "
            f"{id_estado:02d} "
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
                    anio_fin
                    - anio_inicio
                    + 1
                )

                completos = (
                    clima_estado
                    .groupby(
                        [
                            "Idestado",
                            "Idmunicipio",
                        ]
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
                f"Descarga detenida en "
                f"{nombre_estado}: {error}"
            )

            logger.warning(
                "El progreso guardado se conserva."
            )

            raise

        except Exception as error:
            logger.error(
                f"Error procesando "
                f"{nombre_estado}: {error}"
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

        time.sleep(15)

    resumen_estados = pd.DataFrame(
        resumen_estados
    )

    if resumen_estados.empty:
        return resumen_estados

    estados_completos = (
        resumen_estados[
            "Estado_completo"
        ].sum()
    )

    municipios_completos = (
        resumen_estados["Completos"]
        .fillna(0)
        .sum()
    )

    logger.info(
        f"Resumen | "
        f"Estados completos: "
        f"{estados_completos}/{len(ids_estados)} | "
        f"Municipios completos: "
        f"{municipios_completos:,.0f}"
    )

    return resumen_estados

def descargar_clima_todos_estados(
    municipios_clima: pd.DataFrame,
    tamano_lote: int = 2,
    anio_inicio: int = ANIO_INICIAL,
    anio_fin: int = ANIO_FINAL,
    pausa: int = 10,
) -> pd.DataFrame:
    """
    Descarga los datos climáticos de los 32 estados de México.
    """

    return descargar_clima_estados(
        municipios_clima=municipios_clima,
        ids_estados=list(ESTADOS.keys()),
        tamano_lote=tamano_lote,
        anio_inicio=anio_inicio,
        anio_fin=anio_fin,
        pausa=pausa,
    )


def descargar_clima_batch(
    municipios_clima: pd.DataFrame,
    batch: int,
    tamano_lote: int = 2,
    anio_inicio: int = ANIO_INICIAL,
    anio_fin: int = ANIO_FINAL,
    pausa: int = 10,
) -> pd.DataFrame:
    """
    Descarga los datos climáticos correspondientes a un batch.

    Los batches permiten distribuir la descarga entre varios
    integrantes del equipo sin superponer estados.
    """

    if batch not in BATCHES_CLIMA:
        raise ValueError(
            f"Batch no válido: {batch}. "
            f"Opciones disponibles: "
            f"{sorted(BATCHES_CLIMA)}"
        )

    ids_estados = BATCHES_CLIMA[
        batch
    ]

    logger.info(
        f"Batch climático {batch} | "
        f"Estados: "
        f"{ids_estados[0]:02d}-"
        f"{ids_estados[-1]:02d}"
    )

    return descargar_clima_estados(
        municipios_clima=municipios_clima,
        ids_estados=ids_estados,
        tamano_lote=tamano_lote,
        anio_inicio=anio_inicio,
        anio_fin=anio_fin,
        pausa=pausa,
    )