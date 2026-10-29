from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile
import io
import time
import xml.etree.ElementTree as ET
import pandas as pd
import requests
from loguru import logger
from tqdm import tqdm
import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import unary_union
import numpy as np
import folium
from folium.plugins import MarkerCluster
import json
import re
import unicodedata


from proyecto_agronomia.config import (
    CONAGUA_KMZ_URL,
    CONAGUA_KMZ_PATH,
    CONAGUA_RAW_DIR,
    CONAGUA_MEXICO_GEOJSON_URL,
    CONAGUA_DISTANCIA_MIN_KM,
    CONAGUA_INTERIM_DIR,
    CONAGUA_ANIO_INICIAL,
    CONAGUA_ANIO_FINAL,
    CONAGUA_PROCESSED_DIR,
)

MESES_CONAGUA = (
    "ENE", "FEB", "MAR", "ABR",
    "MAY", "JUN", "JUL", "AGO",
    "SEP", "OCT", "NOV", "DIC",
)

def descargar_catalogo_conagua(
    ruta: Path = CONAGUA_KMZ_PATH,
) -> Path:
    """
    Descarga el catálogo nacional KMZ de estaciones
    climatológicas de CONAGUA.

    Si el archivo ya existe, se conserva.

    Parameters
    ----------
    ruta : Path
        Ruta de destino del archivo KMZ.

    Returns
    -------
    Path
        Ruta del catálogo descargado.
    """

    ruta.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if ruta.exists():
        logger.info(
            "El catálogo KMZ de CONAGUA ya existe."
        )
        return ruta

    logger.info(
        "Descargando catálogo nacional de CONAGUA..."
    )

    try:
        respuesta = requests.get(
            CONAGUA_KMZ_URL,
            timeout=120,
        )

        respuesta.raise_for_status()

        contenido = respuesta.content

        if not ZipFile:
            raise ValueError("No se pudo validar el KMZ")

        with ZipFile(io.BytesIO(contenido)) as kmz:
            if not any(
                nombre.lower().endswith(".kml")
                for nombre in kmz.namelist()
            ):
                raise ValueError(
                    "El KMZ no contiene un archivo KML"
                )

        ruta.write_bytes(contenido)

    except (
        requests.RequestException,
        ValueError,
        OSError,
    ) as error:
        logger.error(
            f"Error descargando catálogo CONAGUA: {error}"
        )
        raise

    logger.success(
        f"Catálogo CONAGUA descargado: {ruta.name}"
    )

    return ruta


def descargar_estaciones_conagua(
    estaciones: pd.DataFrame,
    directorio: Path = CONAGUA_RAW_DIR,
    pausa: float = 1.0,
) -> list[Path]:
    """
    Descarga archivos TXT de estadísticas mensuales
    para estaciones CONAGUA.

    Conserva los nombres oficiales de las URL y
    reutiliza archivos descargados anteriormente.
    """

    columnas = {"estacion", "url_mensual"}

    if not columnas.issubset(estaciones.columns):
        raise ValueError(
            f"Se requieren las columnas: {columnas}"
        )

    if pausa < 0:
        raise ValueError(
            "La pausa no puede ser negativa."
        )

    archivos = []

    with requests.Session() as session:

        session.headers.update({
            "User-Agent": "Mozilla/5.0"
        })

        for _, estacion in tqdm(
            estaciones.iterrows(),
            total=len(estaciones),
            desc="Estaciones CONAGUA",
        ):

            clave = str(estacion["estacion"]).strip()
            url = estacion["url_mensual"]

            if not isinstance(url, str):
                logger.warning(
                    f"[{clave}] URL no válida."
                )
                continue

            parsed = urlparse(url.strip())

            if (
                parsed.scheme != "https"
                or parsed.hostname != "smn.conagua.gob.mx"
            ):
                logger.warning(
                    f"[{clave}] Dominio no válido."
                )
                continue

            partes = parsed.path.split("/")

            if "Mensuales" not in partes:
                logger.warning(
                    f"[{clave}] URL mensual no reconocida."
                )
                continue

            indice = partes.index("Mensuales")

            if len(partes) <= indice + 2:
                logger.warning(
                    f"[{clave}] Ruta mensual incompleta."
                )
                continue

            codigo_estado = partes[indice + 1]
            nombre_archivo = partes[indice + 2]

            if (
                not codigo_estado.isalpha()
                or not nombre_archivo.lower().endswith(".txt")
                or "/" in nombre_archivo
            ):
                logger.warning(
                    f"[{clave}] Nombre de archivo no válido."
                )
                continue

            carpeta_estado = directorio / codigo_estado
            carpeta_estado.mkdir(
                parents=True,
                exist_ok=True,
            )

            # Nombre oficial de CONAGUA
            ruta = carpeta_estado / nombre_archivo

            if ruta.is_file():
                archivos.append(ruta)
                continue

            # Compatibilidad con descargas anteriores
            ruta_anterior = (
                carpeta_estado / f"mes{clave}.txt"
            )

            if ruta_anterior.is_file():
                try:
                    ruta_anterior.rename(ruta)

                    logger.info(
                        f"[{clave}] Renombrado: "
                        f"{ruta_anterior.name} → {ruta.name}"
                    )

                    archivos.append(ruta)
                    continue

                except OSError as error:
                    logger.error(
                        f"[{clave}] Error al renombrar: {error}"
                    )
                    continue

            try:
                respuesta = session.get(
                    url,
                    timeout=60,
                )

                respuesta.raise_for_status()

                contenido = respuesta.content
                texto = contenido.decode("utf-8-sig")

                if "ESTADÍSTICA MENSUAL" not in texto:
                    logger.warning(
                        f"[{clave}] Formato no reconocido."
                    )
                    continue

                ruta.write_bytes(contenido)

                logger.success(
                    f"[{clave}] Descargado "
                    f"({len(contenido) / 1024:.1f} KB)"
                )

                archivos.append(ruta)

            except (
                requests.RequestException,
                UnicodeError,
                OSError,
            ) as error:
                logger.error(
                    f"[{clave}] Error: {error}"
                )

            finally:
                time.sleep(pausa)

    logger.success(
        f"Archivos CONAGUA disponibles: "
        f"{len(archivos)} de {len(estaciones)}."
    )

    return archivos

def leer_catalogo_conagua(
    ruta: Path = CONAGUA_KMZ_PATH,
) -> pd.DataFrame:
    """
    Lee el catálogo KMZ de CONAGUA y devuelve
    un DataFrame con los metadatos de las estaciones.

    Parameters
    ----------
    ruta : Path
        Ruta del archivo KMZ.

    Returns
    -------
    pd.DataFrame
        Catálogo nacional de estaciones climatológicas.
    """

    if not ruta.is_file():
        raise FileNotFoundError(
            f"No existe el catálogo KMZ: {ruta}"
        )

    with ZipFile(ruta) as kmz:

        archivo_kml = next(
            (
                nombre
                for nombre in kmz.namelist()
                if nombre.lower().endswith(".kml")
            ),
            None,
        )

        if archivo_kml is None:
            raise ValueError(
                "El KMZ no contiene un archivo KML."
            )

        root = ET.fromstring(
            kmz.read(archivo_kml)
        )

    ns = {
        "kml": "http://www.opengis.net/kml/2.2"
    }

    registros = []

    for placemark in root.findall(
        ".//kml:Placemark", ns
    ):

        datos = {
            elemento.attrib.get("name"): elemento.text
            for elemento in placemark.findall(
                ".//kml:SimpleData", ns
            )
        }

        if not datos.get("CLAVE"):
            continue

        registros.append({
            "estacion": datos.get("CLAVE"),
            "nombre": datos.get("NOMBRE"),
            "estado": datos.get("ESTADO"),
            "municipio": datos.get("MUNICIPIO"),
            "situacion": datos.get("SITUACION"),
            "inicio": datos.get("INICIO"),
            "mas_reciente": datos.get("MAS_RECIENTE"),
            "latitud": datos.get("LATITUD"),
            "longitud": datos.get("LONGITUD"),
            "altitud": datos.get("ALTITUD"),
            "url_mensual": datos.get("MENSUALES"),
        })

    df = pd.DataFrame(registros)

    for columna in [
        "latitud",
        "longitud",
        "altitud",
    ]:
        df[columna] = pd.to_numeric(
            df[columna],
            errors="coerce",
        )

    for columna in [
        "inicio",
        "mas_reciente",
    ]:
        df[columna] = pd.to_datetime(
            df[columna],
            errors="coerce",
        )

    df = df.drop_duplicates(
        subset=["estacion"]
    ).reset_index(drop=True)

    logger.success(
        f"Catálogo CONAGUA leído: "
        f"{len(df):,} estaciones."
    )

    return df

def obtener_territorio_continental():
    """
    Obtiene la geometría del territorio continental de México,
    incluyendo la península de Baja California.

    Excluye los componentes insulares independientes.

    Descarga los límites geográficos desde geoBoundaries
    únicamente cuando no existe una copia local.

    Returns
    -------
    shapely.geometry.base.BaseGeometry
        Geometría del territorio principal de México.
    """

    ruta_geojson = (
        CONAGUA_PROCESSED_DIR
        / "limites_mexico.geojson"
    )

    ruta_geojson.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 1. Descargar el GeoJSON si no existe localmente
    if not ruta_geojson.is_file():

        logger.info(
            "Descargando límites geográficos de México..."
        )

        respuesta = requests.get(
            CONAGUA_MEXICO_GEOJSON_URL,
            timeout=60,
        )
        respuesta.raise_for_status()

        metadata = respuesta.json()

        url_geojson = metadata.get("gjDownloadURL")

        if not url_geojson:
            raise ValueError(
                "geoBoundaries no proporcionó "
                "la URL del archivo GeoJSON."
            )

        respuesta_geojson = requests.get(
            url_geojson,
            timeout=120,
        )
        respuesta_geojson.raise_for_status()

        contenido = respuesta_geojson.json()

        if contenido.get("type") not in (
            "FeatureCollection",
            "Feature",
        ):
            raise ValueError(
                "El archivo descargado no contiene "
                "un GeoJSON válido."
            )

        # Guardar primero en archivo temporal
        ruta_temporal = ruta_geojson.with_suffix(
            ".geojson.tmp"
        )

        try:
            ruta_temporal.write_text(
                json.dumps(
                    contenido,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            ruta_temporal.replace(ruta_geojson)

        finally:
            ruta_temporal.unlink(missing_ok=True)

        logger.success(
            f"GeoJSON descargado: {ruta_geojson}"
        )

    else:

        logger.info(
            "Utilizando límites geográficos "
            "almacenados localmente."
        )

    # 2. Leer el GeoJSON desde el disco
    limites = gpd.read_file(
        ruta_geojson
    ).to_crs("EPSG:4326")

    if limites.empty:
        raise ValueError(
            "El GeoJSON de México no contiene geometrías."
        )

    # 3. Separar los polígonos del territorio mexicano
    poligonos = limites.explode(
        index_parts=False
    )

    # 4. Puntos interiores de referencia
    referencias = [
        Point(-99.1332, 19.4326),    # México continental
        Point(-116.5964, 31.8667),  # Baja California
    ]

    # 5. Seleccionar únicamente los polígonos principales
    seleccionados = [
        geometria
        for geometria in poligonos.geometry
        if geometria is not None
        and not geometria.is_empty
        and any(
            geometria.covers(punto)
            for punto in referencias
        )
    ]

    if not seleccionados:
        raise ValueError(
            "No se identificaron los polígonos "
            "del territorio principal de México."
        )

    # 6. Unificar las geometrías seleccionadas
    territorio = unary_union(seleccionados)

    logger.success(
        "Geometría continental de México obtenida."
    )

    return territorio


def filtrar_estaciones_continentales(
    estaciones: pd.DataFrame,
) -> pd.DataFrame:
    """
    Excluye las estaciones climatológicas ubicadas
    en componentes insulares de México.

    Parameters
    ----------
    estaciones : pd.DataFrame
        Catálogo de estaciones con latitud y longitud.

    Returns
    -------
    pd.DataFrame
        Estaciones ubicadas en el territorio continental
        principal y la península de Baja California.
    """

    columnas = {"latitud", "longitud"}

    if not columnas.issubset(estaciones.columns):
        raise ValueError(
            f"Se requieren las columnas: {columnas}"
        )

    territorio = obtener_territorio_continental()

    df = estaciones.dropna(
        subset=["latitud", "longitud"]
    ).copy()

    puntos = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(
            df["longitud"],
            df["latitud"],
        ),
        crs="EPSG:4326",
    )

    mascara = puntos.geometry.apply(
        territorio.covers
    )

    resultado = (
        puntos.loc[mascara]
        .drop(columns="geometry")
        .reset_index(drop=True)
    )

    logger.success(
        f"Filtro continental: "
        f"{len(resultado):,} estaciones conservadas "
        f"de {len(estaciones):,}."
    )

    return resultado

def seleccionar_estaciones_espaciales(
    estaciones: pd.DataFrame,
    distancia_min_km: float = CONAGUA_DISTANCIA_MIN_KM,
) -> pd.DataFrame:
    """
    Selecciona estaciones geográficamente distribuidas,
    respetando una distancia mínima dentro de cada estado.

    La primera estación se elige por duración potencial
    del periodo de registro. Las siguientes se seleccionan
    maximizando la distancia a las ya elegidas.
    """

    if distancia_min_km <= 0:
        raise ValueError(
            "La distancia mínima debe ser positiva."
        )

    requeridas = {
        "estado", "latitud", "longitud",
        "inicio", "mas_reciente",
    }

    if not requeridas.issubset(estaciones.columns):
        raise ValueError(
            f"Faltan columnas: {requeridas - set(estaciones.columns)}"
        )

    def distancias_haversine(lat, lon, latitudes, longitudes):
        radio = 6371.0088

        lat1 = np.radians(lat)
        lon1 = np.radians(lon)
        lat2 = np.radians(latitudes)
        lon2 = np.radians(longitudes)

        delta_lat = lat2 - lat1
        delta_lon = lon2 - lon1

        a = (
            np.sin(delta_lat / 2) ** 2
            + np.cos(lat1)
            * np.cos(lat2)
            * np.sin(delta_lon / 2) ** 2
        )

        return 2 * radio * np.arcsin(
            np.sqrt(np.clip(a, 0, 1))
        )

    seleccion = []

    for estado, grupo in estaciones.groupby("estado"):

        df = grupo.dropna(
            subset=["latitud", "longitud"]
        ).copy().reset_index(drop=True)

        if df.empty:
            continue

        duracion = (
            df["mas_reciente"] - df["inicio"]
        ).dt.days.fillna(-1)

        inicial = int(duracion.idxmax())

        latitudes = df["latitud"].to_numpy()
        longitudes = df["longitud"].to_numpy()

        distancias_minimas = distancias_haversine(
            latitudes[inicial],
            longitudes[inicial],
            latitudes,
            longitudes,
        )

        indices = [inicial]
        distancias_minimas[inicial] = 0

        while True:
            siguiente = int(np.argmax(distancias_minimas))

            if distancias_minimas[siguiente] < distancia_min_km:
                break

            indices.append(siguiente)

            nuevas_distancias = distancias_haversine(
                latitudes[siguiente],
                longitudes[siguiente],
                latitudes,
                longitudes,
            )

            distancias_minimas = np.minimum(
                distancias_minimas,
                nuevas_distancias,
            )

        seleccion.append(df.iloc[indices])

        logger.info(
            f"{estado}: {len(df)} candidatas → "
            f"{len(indices)} seleccionadas."
        )

    if not seleccion:
        return estaciones.iloc[0:0].copy()

    resultado = pd.concat(
        seleccion,
        ignore_index=True,
    )

    logger.success(
        f"Selección espacial terminada: "
        f"{len(resultado):,} estaciones."
    )

    return resultado

def crear_mapa_estaciones_conagua(
    estaciones: pd.DataFrame,
    agrupar_marcadores: bool = False,
) -> folium.Map:
    """
    Genera un mapa interactivo de estaciones climatológicas.

    Parameters
    ----------
    estaciones : pd.DataFrame
        Estaciones con coordenadas geográficas.
    agrupar_marcadores : bool
        Si True, agrupa los marcadores cercanos.

    Returns
    -------
    folium.Map
        Mapa interactivo de estaciones.
    """

    mapa = folium.Map(
        location=[23.6, -102.5],
        zoom_start=5,
        tiles="OpenStreetMap",
    )

    capa = (
        MarkerCluster().add_to(mapa)
        if agrupar_marcadores
        else mapa
    )

    for estacion in estaciones.itertuples():

        popup = (
            f"<b>Estación:</b> {estacion.estacion}<br>"
            f"<b>Nombre:</b> {estacion.nombre}<br>"
            f"<b>Estado:</b> {estacion.estado}<br>"
            f"<b>Municipio:</b> {estacion.municipio}"
        )

        folium.CircleMarker(
            location=[
                estacion.latitud,
                estacion.longitud,
            ],
            radius=3,
            color="#1769aa",
            fill=True,
            fill_opacity=0.75,
            popup=folium.Popup(
                popup,
                max_width=300,
            ),
        ).add_to(capa)

    logger.success(
        f"Mapa generado con {len(estaciones)} estaciones."
    )

    return mapa

def _normalizar_conagua(texto: str) -> str:
    """Normaliza acentos, espacios y mayúsculas."""

    texto = unicodedata.normalize("NFKD", texto)

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )

    return " ".join(texto.upper().split())


def _convertir_valor_conagua(texto: str):
    """Convierte una observación numérica o faltante."""

    valor = texto.strip()

    if not valor or valor.upper() in {
        "N/D", "ND", "NA", "NAN", "-", "S/D",
    }:
        return None

    try:
        return float(valor.replace(",", ""))
    except ValueError:
        return None


def convertir_txt_conagua(
    ruta_txt: Path,
    ruta_json: Path | None = None,
    anio_inicial: int = CONAGUA_ANIO_INICIAL,
    anio_final: int = CONAGUA_ANIO_FINAL,
) -> Path:
    """
    Convierte un TXT mensual de CONAGUA a JSON.

    Conserva las secciones climatológicas encontradas
    y sus observaciones mensuales dentro del periodo
    solicitado.
    """

    ruta_txt = Path(ruta_txt)

    if ruta_json is None:
        relativa = ruta_txt.relative_to(CONAGUA_RAW_DIR)

        ruta_json = (
            CONAGUA_INTERIM_DIR
            / relativa.with_suffix(".json")
        )

    ruta_json = Path(ruta_json)
    ruta_json.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    contenido = ruta_txt.read_text(
        encoding="utf-8-sig"
    )

    lineas = contenido.splitlines()

    datos = {
        "estacion": ruta_txt.stem.removeprefix("mes"),
        "archivo_origen": str(
            ruta_txt.relative_to(CONAGUA_RAW_DIR)
        ),
        "periodo": {
            "inicio": anio_inicial,
            "fin": anio_final,
        },
        "variables": {},
    }

    encabezado_meses = re.compile(
        r"^A[NÑ]O\s+ENE\s+FEB\s+MAR\s+ABR\s+"
        r"MAY\s+JUN\s+JUL\s+AGO\s+SEP\s+OCT\s+NOV\s+DIC\b"
    )

    fila_anual = re.compile(r"^\d{4}$")

    seccion = None
    esperando_seccion = None
    leyendo_tabla = False

    for linea in lineas:

        texto = linea.strip()

        if not texto:
            continue

        normalizado = _normalizar_conagua(texto)

        # Detectar encabezado de tabla mensual
        if encabezado_meses.match(normalizado):

            seccion = esperando_seccion

            if seccion:
                datos["variables"].setdefault(
                    seccion, []
                )

            leyendo_tabla = bool(seccion)
            continue

        # Detectar filas anuales
        columnas = re.split(r"\t+", linea.strip())

        if (
            leyendo_tabla
            and columnas
            and fila_anual.fullmatch(columnas[0].strip())
        ):

            anio = int(columnas[0].strip())

            if anio_inicial <= anio <= anio_final:

                valores = columnas[1:13]

                # Conservar columnas mensuales vacías
                valores += [""] * (12 - len(valores))

                for mes, valor in enumerate(
                    valores[:12],
                    start=1,
                ):
                    datos["variables"][seccion].append({
                        "anio": anio,
                        "mes": mes,
                        "valor": _convertir_valor_conagua(
                            valor
                        ),
                    })

            continue

        # Detectar el título de la siguiente sección
        if not fila_anual.fullmatch(
            normalizado.split()[0]
        ):
            leyendo_tabla = False

            # Evitar confundir filas de resumen
            # con nombres de variables.
            if not normalizado.startswith(
                ("TOTAL", "PROMEDIO", "MAXIMO", "MINIMO")
            ):
                esperando_seccion = normalizado

    if not datos["variables"]:
        raise ValueError(
            f"No se encontraron tablas mensuales en {ruta_txt}"
        )

    ruta_json.write_text(
        json.dumps(
            datos,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return ruta_json

def convertir_conagua_nacional(
    directorio_raw: Path = CONAGUA_RAW_DIR,
    directorio_json: Path = CONAGUA_INTERIM_DIR,
    sobrescribir: bool = False,
) -> dict:
    """
    Convierte todos los TXT mensuales de CONAGUA a JSON.

    Parameters
    ----------
    directorio_raw : Path
        Directorio con los TXT originales.
    directorio_json : Path
        Directorio de salida para los JSON.
    sobrescribir : bool
        Si True, vuelve a generar los JSON existentes.

    Returns
    -------
    dict
        Resumen del procesamiento nacional.
    """

    archivos_txt = sorted(
        directorio_raw.rglob("mes*.txt")
    )

    logger.info(
        f"Se encontraron {len(archivos_txt)} archivos TXT."
    )

    convertidos = []
    existentes = []
    errores = []

    for ruta_txt in tqdm(
        archivos_txt,
        desc="Convirtiendo CONAGUA a JSON",
    ):

        # Mantener la estructura de carpetas por estado
        ruta_relativa = ruta_txt.relative_to(
            directorio_raw
        )

        ruta_json = (
            directorio_json
            / ruta_relativa.with_suffix(".json")
        )

        if ruta_json.is_file() and not sobrescribir:
            existentes.append(ruta_json)
            continue

        try:
            ruta_generada = convertir_txt_conagua(
                ruta_txt=ruta_txt,
                ruta_json=ruta_json,
            )

            convertidos.append(ruta_generada)

        except Exception as error:
            logger.error(
                f"Error procesando {ruta_txt.name}: {error}"
            )

            errores.append({
                "archivo": str(ruta_txt),
                "error": str(error),
            })

    resumen = {
        "total_txt": len(archivos_txt),
        "convertidos": len(convertidos),
        "existentes": len(existentes),
        "errores": len(errores),
        "detalle_errores": errores,
    }

    logger.success(
        f"Procesamiento CONAGUA terminado. "
        f"Convertidos: {len(convertidos)} | "
        f"Existentes: {len(existentes)} | "
        f"Errores: {len(errores)}"
    )

    return resumen

def cargar_json_conagua(
    directorio: Path = CONAGUA_INTERIM_DIR,
) -> pd.DataFrame:
    """
    Lee los archivos JSON climatológicos de CONAGUA
    y construye un DataFrame nacional en formato largo.

    Returns
    -------
    pd.DataFrame
        Observaciones mensuales por estación y variable.
    """

    archivos = sorted(
        directorio.rglob("mes*.json")
    )

    registros = []
    errores = []

    for ruta in tqdm(
        archivos,
        desc="Leyendo JSON CONAGUA",
    ):
        try:
            with ruta.open(
                encoding="utf-8"
            ) as archivo:
                datos = json.load(archivo)

            estacion = str(datos["estacion"])

            for variable, observaciones in (
                datos["variables"].items()
            ):
                for observacion in observaciones:
                    registros.append({
                        "estacion": estacion,
                        "variable": variable,
                        "anio": observacion["anio"],
                        "mes": observacion["mes"],
                        "valor": observacion["valor"],
                    })

        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
        ) as error:
            errores.append({
                "archivo": str(ruta),
                "error": str(error),
            })

    df = pd.DataFrame(
        registros,
        columns=[
            "estacion",
            "variable",
            "anio",
            "mes",
            "valor",
        ],
    )

    if not df.empty:
        df["anio"] = pd.to_numeric(
            df["anio"], errors="coerce"
        )

        df["mes"] = pd.to_numeric(
            df["mes"], errors="coerce"
        )

        df["valor"] = pd.to_numeric(
            df["valor"], errors="coerce"
        )

    logger.success(
        f"CONAGUA: {len(archivos)} JSON leídos, "
        f"{len(df):,} observaciones extraídas, "
        f"{len(errores)} archivos con errores."
    )

    if errores:
        logger.warning(
            f"Primeros errores: {errores[:5]}"
        )

    return df

def crear_geodataframe_conagua(
    df_estaciones: pd.DataFrame,
    df_cobertura: pd.DataFrame,
    validation: str = "one_to_one",
) -> gpd.GeoDataFrame:
    """
    Une el catálogo de estaciones con indicadores
    de cobertura climática y crea un GeoDataFrame.
    """

    estaciones = df_estaciones.copy()
    cobertura = df_cobertura.copy()

    estaciones["estacion"] = normalizar_clave_conagua(
        estaciones["estacion"]
    )

    cobertura["estacion"] = normalizar_clave_conagua(
        cobertura["estacion"]
    )

    estaciones["latitud"] = pd.to_numeric(
        estaciones["latitud"], errors="coerce"
    )

    estaciones["longitud"] = pd.to_numeric(
        estaciones["longitud"], errors="coerce"
    )

    df = estaciones.merge(
        cobertura,
        on="estacion",
        how="left",
        validate= validation,
    )

    df = df.dropna(subset=["latitud", "longitud"])

    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(
            df["longitud"],
            df["latitud"],
        ),
        crs="EPSG:4326",
    )

    return gdf

def normalizar_clave_conagua(serie: pd.Series) -> pd.Series:
    """
    Normaliza las claves de estaciones CONAGUA
    a cinco dígitos, conservando los ceros iniciales.
    """
    return (
        serie.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(5)
    )

def calcular_precipitacion_media_anual(
    df_clima: pd.DataFrame,
    anio_inicial: int = CONAGUA_ANIO_INICIAL,
    anio_final: int = CONAGUA_ANIO_FINAL,
    min_anios: int = 10,
) -> pd.DataFrame:
    """
    Calcula la precipitación media anual por estación.

    Solo considera años con 12 meses válidos.
    Requiere al menos min_anios años completos.
    """

    df = df_clima[
        (df_clima["variable"] == "LLUVIA TOTAL MENSUAL")
        & df_clima["anio"].between(anio_inicial, anio_final)
        & df_clima["mes"].between(1, 12)
    ].copy()

    df["estacion"] = normalizar_clave_conagua(
        df["estacion"]
    )

    # No sumar duplicados silenciosamente
    claves = ["estacion", "anio", "mes"]

    if df.duplicated(claves).any():
        raise ValueError(
            "Existen observaciones mensuales duplicadas."
        )

    # Agregación por estación y año
    df_anual = (
        df.groupby(["estacion", "anio"])
        .agg(
            precipitacion_anual=("valor", "sum"),
            meses_validos=("valor", "count"),
        )
        .reset_index()
    )

    # Conservar exclusivamente años completos
    df_anual = df_anual[
        df_anual["meses_validos"] == 12
    ]

    # Promedio de los acumulados anuales
    resultado = (
        df_anual.groupby("estacion")
        .agg(
            precipitacion_media_anual=(
                "precipitacion_anual", "mean"
            ),
            anios_completos=("anio", "nunique"),
        )
        .reset_index()
    )

    resultado.loc[
        resultado["anios_completos"] < min_anios,
        "precipitacion_media_anual",
    ] = float("nan")

    return resultado

def calcular_precipitacion_por_anio(
    df_clima: pd.DataFrame,
    anio_inicial: int = CONAGUA_ANIO_INICIAL,
    anio_final: int = CONAGUA_ANIO_FINAL,
) -> pd.DataFrame:

    df = df_clima[
        (df_clima["variable"] == "LLUVIA TOTAL MENSUAL")
        & df_clima["anio"].between(anio_inicial, anio_final)
        & df_clima["mes"].between(1, 12)
    ].copy()

    df["estacion"] = normalizar_clave_conagua(
        df["estacion"]
    )

    claves = ["estacion", "anio", "mes"]

    if df.duplicated(claves).any():
        raise ValueError(
            "Existen registros mensuales duplicados."
        )

    df_anual = (
        df.groupby(["estacion", "anio"])
        .agg(
            precipitacion_anual=("valor", "sum"),
            meses_validos=("valor", "count"),
        )
        .reset_index()
    )

    # Excluir años con meses faltantes
    df_anual = df_anual[
        df_anual["meses_validos"] == 12
    ].copy()

    return df_anual

def preparar_clima_anual_integracion(
    df_clima: pd.DataFrame,
    anio_inicial: int = 2003,
    anio_final: int = 2025,
) -> pd.DataFrame:
    """
    Organiza observaciones mensuales CONAGUA en una tabla
    anual por estación.

    Genera todos los años del periodo solicitado para
    cada estación.

    Solo calcula indicadores anuales cuando existen
    12 meses válidos. En caso contrario conserva NaN.

    Returns
    -------
    pd.DataFrame
        Tabla anual con cobertura completa de años.
    """

    variables = {
        "LLUVIA TOTAL MENSUAL": (
            "precipitacion_anual_mm",
            "sum",
            "meses_precipitacion",
        ),
        "TEMPERATURA MEDIA MENSUAL": (
            "temperatura_media_c",
            "mean",
            "meses_temperatura",
        ),
    }

    df = df_clima.copy()

    df["estacion"] = normalizar_clave_conagua(
        df["estacion"]
    )

    df = df[
        df["anio"].between(anio_inicial, anio_final)
        & df["mes"].between(1, 12)
        & df["variable"].isin(variables)
    ].copy()

    # Evitar agregar observaciones duplicadas.
    claves = ["estacion", "anio", "mes", "variable"]

    if df.duplicated(claves).any():
        raise ValueError(
            "Existen observaciones mensuales duplicadas."
        )

    estaciones = (
        normalizar_clave_conagua(df_clima["estacion"])
        .dropna()
        .drop_duplicates()
        .sort_values()
    )

    # Crear todas las combinaciones estación-año.
    indice = pd.MultiIndex.from_product(
        [
            estaciones,
            range(anio_inicial, anio_final + 1),
        ],
        names=["estacion", "anio"],
    )

    resultado = indice.to_frame(index=False)

    for variable, (
        nombre_indicador,
        operacion,
        nombre_cobertura,
    ) in variables.items():

        datos = df[df["variable"] == variable]

        anual = (
            datos.groupby(["estacion", "anio"])
            .agg(
                **{
                    nombre_indicador: (
                        "valor",
                        operacion,
                    ),
                    nombre_cobertura: (
                        "valor",
                        "count",
                    ),
                }
            )
            .reset_index()
        )

        # No utilizar indicadores de años incompletos.
        anual.loc[
            anual[nombre_cobertura] < 12,
            nombre_indicador,
        ] = np.nan

        resultado = resultado.merge(
            anual,
            on=["estacion", "anio"],
            how="left",
            validate="one_to_one",
        )

        # Sin registros significa cero meses disponibles.
        resultado[nombre_cobertura] = (
            resultado[nombre_cobertura]
            .fillna(0)
            .astype(int)
        )

    return resultado.sort_values(
        ["estacion", "anio"]
    ).reset_index(drop=True)

def guardar_clima_anual(
    df_clima_anual: pd.DataFrame,
    directorio: Path = CONAGUA_PROCESSED_DIR,
) -> Path:
    """
    Guarda los indicadores climáticos anuales
    en formato CSV.
    """

    directorio.mkdir(
        parents=True,
        exist_ok=True,
    )

    ruta = directorio / "clima_anual_2003_2025.csv"

    df_clima_anual.to_csv(
        ruta,
        index=False,
        encoding="utf-8-sig",
        na_rep="",
    )

    logger.success(
        f"Clima anual guardado: {ruta}"
    )

    return ruta