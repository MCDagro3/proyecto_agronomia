from pathlib import Path
import re
import time
import zipfile

import geopandas as gpd
from loguru import logger
import requests
from tqdm import tqdm

from proyecto_agronomia.config import (
    INEGI_ESTADOS_URL_TEMPLATE,
    INEGI_INTERIM_DIR,
    INEGI_MAPAS_API_URL,
    INEGI_MAPAS_HOST,
    INEGI_MUNICIPIOS_URL_TEMPLATE,
    INEGI_USV_RAW_DIR,
)

SERIES_USO_SUELO = ("I", "II", "III", "IV", "V", "VI", "VII")
CONSULTA_USO_SUELO = {
    "enti": "",
    "muni": "",
    "loca": "",
    "tema": "",
    "titg": "",
    "esca": 2,
    "edic": "",
    "form": 9,
    "prog": "",
    "busc": "uso del suelo y vegetación",
    "tipoB": 1,
    "adv": False,
    "rango": "",
    "sens": "",
    "uedo": "",
    "reso": "",
    "point": "",
    "malla": "",
    "poligono": "",
    "buscAG": None,
    "orden": 4,
    "desc": True,
    "pag": 0,
    "tam": 100,
}
PATRON_SERIE_NACIONAL = re.compile(
    r"[Ss]erie\s*\(?([IVX]+)\)?\s*\.?\s*(Conjunto|Continuo)\s+Nacional\.?\s*$"
)


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

        url = INEGI_MUNICIPIOS_URL_TEMPLATE.format(clave_estado=clave_estado)

        logger.info(f"Descargando municipios del estado {clave_estado}.")

        try:
            respuesta = requests.get(
                url,
                timeout=120,
            )

            respuesta.raise_for_status()
            datos = respuesta.json()

        except requests.RequestException as error:
            logger.error(f"Error descargando estado {clave_estado}: {error}")
            raise

        features.extend(datos["features"])

    municipios_geo = gpd.GeoDataFrame.from_features(
        features,
        crs="EPSG:4326",
    )

    municipios_geo.to_file(
        ruta_geojson,
        driver="GeoJSON",
    )

    logger.success(f"Municipios INEGI guardados: {len(municipios_geo):,}")

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

        url = INEGI_ESTADOS_URL_TEMPLATE.format(clave_estado=clave_estado)

        logger.info(f"Descargando estado {clave_estado}.")

        try:
            respuesta = requests.get(
                url,
                timeout=60,
            )
            respuesta.raise_for_status()
            datos = respuesta.json()

        except requests.RequestException as error:
            logger.error(f"Error descargando estado {clave_estado}: {error}")
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

    logger.success(f"Entidades geográficas guardadas: {len(estados_geo)}")

    return estados_geo


def _post_mapas_inegi(
    endpoint: str,
    payload: dict,
    intentos: int = 4,
    sesion: requests.Session | None = None,
) -> dict:
    """Consulta la API cartográfica de INEGI con reintentos."""
    cliente = sesion or requests.Session()
    cliente.headers.update({"User-Agent": "Mozilla/5.0"})
    url = f"{INEGI_MAPAS_API_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    for intento in range(intentos):
        try:
            respuesta = cliente.post(url, json=payload, timeout=60)
            respuesta.raise_for_status()
            return respuesta.json()
        except requests.RequestException:
            if intento == intentos - 1:
                raise
            time.sleep(2 * (intento + 1))
    raise RuntimeError("No fue posible consultar la API cartográfica de INEGI.")


def buscar_mapas_inegi(
    consulta: dict | None = None,
    sesion: requests.Session | None = None,
) -> list[dict]:
    """Recorre todas las páginas del catálogo cartográfico de INEGI."""
    parametros = dict(CONSULTA_USO_SUELO if consulta is None else consulta)
    mapas: list[dict] = []
    pagina = 0
    while True:
        parametros["pag"] = pagina
        datos = _post_mapas_inegi("lista/resultados", parametros, sesion=sesion)
        if not datos.get("success"):
            raise RuntimeError(f"INEGI rechazó la consulta: {datos}")
        lote = datos.get("list", {}).get("mapas", [])
        if not lote:
            break
        mapas.extend(lote)
        if len(lote) < int(parametros.get("tam", 100)):
            break
        pagina += 1
    return mapas


def catalogo_uso_suelo_nacional(
    consulta: dict | None = None,
    sesion: requests.Session | None = None,
) -> dict[str, dict]:
    """Obtiene el producto nacional SHP de cada serie de uso del suelo."""
    catalogo: dict[str, dict] = {}
    for mapa in buscar_mapas_inegi(consulta=consulta, sesion=sesion):
        titulo = mapa.get("titulo", "").strip()
        coincide = PATRON_SERIE_NACIONAL.search(titulo)
        if not coincide or mapa.get("entidad") != "Estados Unidos Mexicanos":
            continue
        shp = next(
            (formato for formato in mapa.get("formatos", []) if formato.get("extension") == "SHP"),
            None,
        )
        if shp is None:
            continue
        valor_url = shp.get("url", {}).get("valor")
        if not valor_url:
            continue
        catalogo[coincide.group(1)] = {
            "key": mapa.get("key"),
            "titulo": titulo,
            "edicion": mapa.get("edicion"),
            "url": f"{INEGI_MAPAS_HOST.rstrip('/')}/{valor_url.lstrip('/')}",
            "peso": shp.get("peso"),
        }
    return catalogo


def descargar_archivo_inegi(
    url: str,
    destino: Path,
    intentos: int = 4,
    sesion: requests.Session | None = None,
) -> Path:
    """Descarga un archivo INEGI de forma atómica y reutiliza el existente."""
    if destino.exists():
        logger.info(f"Ya existe {destino.name}.")
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".part")
    cliente = sesion or requests.Session()
    cliente.headers.update({"User-Agent": "Mozilla/5.0"})
    for intento in range(intentos):
        try:
            with cliente.get(url, stream=True, timeout=120) as respuesta:
                respuesta.raise_for_status()
                with temporal.open("wb") as archivo:
                    for bloque in respuesta.iter_content(chunk_size=1 << 20):
                        if bloque:
                            archivo.write(bloque)
            temporal.replace(destino)
            return destino
        except requests.RequestException:
            temporal.unlink(missing_ok=True)
            if intento == intentos - 1:
                raise
            time.sleep(2 * (intento + 1))
    raise RuntimeError(f"No se pudo descargar {url}")


def descargar_series_uso_suelo(
    series: tuple[str, ...] = SERIES_USO_SUELO,
    directorio: Path = INEGI_USV_RAW_DIR,
    extraer: bool = False,
) -> dict[str, Path]:
    """Descarga las series nacionales de uso del suelo y vegetación."""
    invalidas = sorted(set(series) - set(SERIES_USO_SUELO))
    if invalidas:
        raise ValueError(f"Series no válidas: {invalidas}")
    catalogo = catalogo_uso_suelo_nacional()
    rutas: dict[str, Path] = {}
    for serie in series:
        if serie not in catalogo:
            logger.warning(f"Serie {serie}: no localizada en el catálogo.")
            continue
        informacion = catalogo[serie]
        nombre = f"usv_250k_serie_{serie}_{informacion['key']}.zip"
        ruta = descargar_archivo_inegi(informacion["url"], directorio / nombre)
        if not zipfile.is_zipfile(ruta):
            raise ValueError(f"El archivo descargado no es un ZIP válido: {ruta}")
        rutas[serie] = ruta
        if extraer:
            destino_extraccion = ruta.with_suffix("")
            destino_extraccion.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(ruta) as comprimido:
                comprimido.extractall(destino_extraccion)
    return rutas
