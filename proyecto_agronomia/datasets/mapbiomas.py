"""Descarga de la cobertura y uso del suelo de MapBiomas México (Colección 1).

El bucket público de MapBiomas (``mapbiomas-public``) tiene suspendida la
descarga de GeoTIFF. Este módulo usa la API de la plataforma
(https://plataforma.mapbiomas.org), la misma que ejecuta su botón
"descargar": se solicita una exportación por territorio y años, se espera a
que esté lista y se baja el TIFF desde una URL firmada de corta duración.

La API no está documentada públicamente y puede cambiar. Los TIFF crudos se
conservan en ``data/raw/mapbiomas/<clave>/<anio>.tif`` (``00`` = nacional) para no
depender de ella una vez descargados.

Datos: MapBiomas – Colección 1 de la Serie Anual de Mapas de Cobertura y Uso
del Suelo de México, licencia CC BY 4.0.
"""

from collections.abc import Iterable
import json
from pathlib import Path
import time

from loguru import logger
import requests

from proyecto_agronomia.config import (
    ANIOS_MAPBIOMAS,
    MAPBIOMAS_API_URL,
    MAPBIOMAS_RAW_DIR,
)

# Clases del grupo 14 "Agropecuario" de la leyenda oficial (API ``/legends``)
# que se usan como filtro. Se excluyen 9 "Plantación forestal" y 21 "Mosaico
# de usos" (agricultura mezclada con vegetación natural, demasiado ambigua).
CLASES_AGRICOLAS_MAPBIOMAS = {
    15: "Pastizal cultivado e inducido",
    19: "Cultivo anual",
    36: "Cultivo perenne",
}

# Máscara -> clases MapBiomas que la componen. Cada registro SIAP se asigna a
# una máscara en ``processing.integracion_mapbiomas.asignar_mascara_mapbiomas``.
# ``agricola`` es auxiliar (ningún registro se asigna a ella): la unión 19+36
# sirve de respaldo a los perennes, porque MapBiomas clasifica como cultivo
# anual buena parte de la caña, cítricos, alfalfa y vid.
MASCARAS_MAPBIOMAS = {
    "anual": frozenset({19}),
    "perenne": frozenset({36}),
    "pastizal": frozenset({15}),
    "agricola": frozenset({19, 36}),
}

# Máscara del registro -> máscara a usar si la propia mide menos del umbral.
RESPALDOS_MASCARA = {"perenne": "agricola"}

SUBTEMA_COBERTURA = "coverage_lclu"
CATEGORIA_ESTADO = 2
ESTADOS_ACTIVOS = {"QUEUED", "EXPORTING", "MOSAICKING", "CLIPPING"}
ESTADO_LISTO = "READY"
ENCABEZADOS = {"tenant-id": "mapbiomas", "User-Agent": "proyecto-agronomia/0.1"}
TIMEOUT = 60
ARCHIVO_MANIFIESTO = "manifiesto_exportaciones.json"
# Aunque la API acepta listas de años al crear la exportación, solo procesa
# las de un año ("Invalid number of years provided" en otro caso).
TERRITORIO_NACIONAL = "37-1-1"
CLAVE_NACIONAL = "00"
MAX_EXPORTACIONES_ACTIVAS = 3
MAX_REINTENTOS_EXPORTACION = 2


def _sesion() -> requests.Session:
    sesion = requests.Session()
    sesion.headers.update(ENCABEZADOS)
    return sesion


def _peticion(
    sesion: requests.Session,
    metodo: str,
    url: str,
    reintentos: int = 6,
    pausa_inicial: float = 10.0,
    **kwargs,
) -> requests.Response:
    """Petición con reintentos ante errores de red, 409, 422, 429 y 5xx."""
    pausa = pausa_inicial
    for intento in range(1, reintentos + 1):
        try:
            respuesta = sesion.request(metodo, url, timeout=TIMEOUT, **kwargs)
        except requests.RequestException as error:
            if intento == reintentos:
                raise
            logger.warning(f"Error de red ({error}); reintento {intento} en {pausa:.0f} s.")
        else:
            if respuesta.status_code < 400:
                return respuesta
            reintentable = respuesta.status_code in {409, 422, 429} or (
                respuesta.status_code >= 500
            )
            if not reintentable or intento == reintentos:
                respuesta.raise_for_status()
            logger.warning(
                f"HTTP {respuesta.status_code} en {url}; reintento {intento} en {pausa:.0f} s."
            )
        time.sleep(pausa)
        pausa = min(pausa * 2, 300)
    raise RuntimeError("Reintentos agotados.")  # pragma: no cover


def obtener_territorios_estatales(
    sesion: requests.Session | None = None,
) -> dict[str, str]:
    """Devuelve ``{clave INEGI de 2 dígitos: id de territorio MapBiomas}``."""
    sesion = sesion or _sesion()
    territorios: dict[str, str] = {}
    pagina, paginas = 1, 1
    while pagina <= paginas:
        datos = _peticion(
            sesion,
            "GET",
            f"{MAPBIOMAS_API_URL}/territories",
            params={"categoryId": CATEGORIA_ESTADO, "page": pagina},
        ).json()
        paginas = datos["numberOfPages"]
        for territorio in datos["territories"]:
            if territorio["categoryId"] == CATEGORIA_ESTADO:
                territorios[str(territorio["geocode"]).zfill(2)] = territorio["id"]
        pagina += 1
    if len(territorios) != 32:
        raise ValueError(f"Se esperaban 32 estados y se obtuvieron {len(territorios)}.")
    return dict(sorted(territorios.items()))


def solicitar_exportacion(
    territorio: str,
    anios: Iterable[int],
    sesion: requests.Session | None = None,
) -> list[dict]:
    """Solicita la exportación de cobertura y devuelve los trabajos creados."""
    sesion = sesion or _sesion()
    cuerpo = {
        "territoryId": territorio,
        "subthemeKey": SUBTEMA_COBERTURA,
        "years": sorted(int(anio) for anio in anios),
    }
    respuesta = _peticion(sesion, "POST", f"{MAPBIOMAS_API_URL}/maps/exports", json=cuerpo)
    return respuesta.json()["exports"]


def consultar_exportacion(id_exportacion: str, sesion: requests.Session | None = None) -> dict:
    sesion = sesion or _sesion()
    return _peticion(sesion, "GET", f"{MAPBIOMAS_API_URL}/maps/exports/{id_exportacion}").json()


def esperar_exportacion(
    id_exportacion: str,
    sesion: requests.Session | None = None,
    intervalo: float = 15.0,
    tiempo_maximo: float = 4 * 3600,
) -> dict:
    """Espera a que la exportación termine y devuelve su estado final."""
    sesion = sesion or _sesion()
    inicio = time.monotonic()
    while True:
        estado = consultar_exportacion(id_exportacion, sesion)
        if estado["status"] == ESTADO_LISTO:
            return estado
        if estado["status"] not in ESTADOS_ACTIVOS:
            raise RuntimeError(
                f"Exportación {id_exportacion} terminó en {estado['status']}: "
                f"{estado.get('errorMessage')}"
            )
        if time.monotonic() - inicio > tiempo_maximo:
            raise TimeoutError(f"Exportación {id_exportacion} sigue en {estado['status']}.")
        time.sleep(intervalo)


def descargar_exportacion(
    id_exportacion: str,
    destino: Path,
    sesion: requests.Session | None = None,
) -> Path:
    """Descarga el TIFF de una exportación lista.

    La URL firmada vence en minutos, así que se solicita justo antes de bajar.
    Se escribe primero a un archivo temporal para no dejar descargas truncadas.
    """
    sesion = sesion or _sesion()
    estado = consultar_exportacion(id_exportacion, sesion)
    if estado["status"] != ESTADO_LISTO or not estado.get("downloadUrl"):
        raise RuntimeError(f"Exportación {id_exportacion} no está lista: {estado['status']}")
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".part")
    with requests.get(estado["downloadUrl"], stream=True, timeout=TIMEOUT) as respuesta:
        respuesta.raise_for_status()
        with temporal.open("wb") as archivo:
            for bloque in respuesta.iter_content(chunk_size=1 << 20):
                archivo.write(bloque)
    temporal.replace(destino)
    return destino


def ruta_raster_mapbiomas(
    clave_estado: str, anio: int, directorio: Path = MAPBIOMAS_RAW_DIR
) -> Path:
    return Path(directorio) / str(clave_estado).zfill(2) / f"{anio}.tif"


def _leer_manifiesto(directorio: Path) -> dict:
    ruta = directorio / ARCHIVO_MANIFIESTO
    return json.loads(ruta.read_text()) if ruta.exists() else {}


def _guardar_manifiesto(directorio: Path, manifiesto: dict) -> None:
    ruta = directorio / ARCHIVO_MANIFIESTO
    ruta.write_text(json.dumps(manifiesto, indent=2, sort_keys=True))


def descargar_mapbiomas(
    anios: Iterable[int] = ANIOS_MAPBIOMAS,
    claves_estado: Iterable[str] | None = None,
    directorio: Path = MAPBIOMAS_RAW_DIR,
    max_activas: int = MAX_EXPORTACIONES_ACTIVAS,
    intervalo: float = 15.0,
) -> dict[str, list[Path]]:
    """Descarga la cobertura MapBiomas, un TIFF por territorio y año.

    Por omisión descarga el territorio nacional (``claves_estado=None``) en
    ``<directorio>/00/<anio>.tif``. Con ``claves_estado`` descarga esos
    estados en ``<directorio>/<clave>/<anio>.tif``.

    Mantiene a lo sumo ``max_activas`` exportaciones en proceso para no
    saturar el servicio. Es idempotente: omite archivos existentes y reanuda
    las exportaciones registradas en el manifiesto. El servidor reutiliza
    exportaciones idénticas ya generadas, que quedan listas al instante.
    """
    sesion = _sesion()
    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)
    anios = sorted(int(anio) for anio in anios)
    if claves_estado is None:
        territorios = {CLAVE_NACIONAL: TERRITORIO_NACIONAL}
    else:
        estatales = obtener_territorios_estatales(sesion)
        territorios = {str(c).zfill(2): estatales[str(c).zfill(2)] for c in claves_estado}

    tareas = [
        (clave, anio)
        for clave in territorios
        for anio in anios
        if not ruta_raster_mapbiomas(clave, anio, directorio).exists()
    ]
    logger.info(f"MapBiomas: {len(tareas)} archivos por descargar.")
    manifiesto = _leer_manifiesto(directorio)
    intentos: dict[tuple[str, int], int] = {}
    activas: dict[tuple[str, int], str] = {}
    fallidas: list[tuple[str, int, str]] = []

    while tareas or activas:
        while tareas and len(activas) < max_activas:
            tarea = tareas.pop(0)
            llave = f"{tarea[0]}_{tarea[1]}"
            if llave not in manifiesto:
                exportacion = solicitar_exportacion(territorios[tarea[0]], [tarea[1]], sesion)[0]
                manifiesto[llave] = exportacion["id"]
                _guardar_manifiesto(directorio, manifiesto)
            activas[tarea] = manifiesto[llave]
        for tarea, id_exportacion in list(activas.items()):
            estado = consultar_exportacion(id_exportacion, sesion)
            if estado["status"] in ESTADOS_ACTIVOS:
                continue
            del activas[tarea]
            llave = f"{tarea[0]}_{tarea[1]}"
            if estado["status"] == ESTADO_LISTO:
                descargar_exportacion(
                    id_exportacion, ruta_raster_mapbiomas(*tarea, directorio), sesion
                )
                logger.info(f"MapBiomas {tarea[0]}/{tarea[1]} descargado.")
                continue
            # Fallida o expirada: se olvida el id y se vuelve a solicitar.
            manifiesto.pop(llave, None)
            _guardar_manifiesto(directorio, manifiesto)
            intentos[tarea] = intentos.get(tarea, 0) + 1
            mensaje = f"{estado['status']}: {estado.get('errorMessage')}"
            if intentos[tarea] <= MAX_REINTENTOS_EXPORTACION:
                logger.warning(f"MapBiomas {llave} {mensaje}; se reintenta.")
                tareas.append(tarea)
            else:
                logger.error(f"MapBiomas {llave} {mensaje}; se abandona.")
                fallidas.append((*tarea, mensaje))
        if activas:
            time.sleep(intervalo)

    if fallidas:
        raise RuntimeError(f"Exportaciones MapBiomas fallidas: {fallidas}")
    resultado = {
        clave: [ruta_raster_mapbiomas(clave, anio, directorio) for anio in anios]
        for clave in territorios
    }
    logger.success(f"MapBiomas: {len(resultado)} territorio(s) × {len(anios)} años disponibles.")
    return resultado


def listar_rasters_mapbiomas(
    directorio: Path = MAPBIOMAS_RAW_DIR,
    anios: Iterable[int] = ANIOS_MAPBIOMAS,
) -> dict[str, dict[int, Path]]:
    """Devuelve ``{clave_estado: {anio: ruta}}`` y valida que no falten años."""
    directorio = Path(directorio)
    anios = sorted(int(anio) for anio in anios)
    rasters: dict[str, dict[int, Path]] = {}
    for carpeta in sorted(p for p in directorio.iterdir() if p.is_dir()):
        if not (carpeta.name.isdigit() and len(carpeta.name) == 2):
            continue
        rutas = {anio: carpeta / f"{anio}.tif" for anio in anios}
        faltantes = [anio for anio, ruta in rutas.items() if not ruta.exists()]
        if faltantes:
            raise FileNotFoundError(f"Estado {carpeta.name}: faltan los años {faltantes}.")
        rasters[carpeta.name] = rutas
    if not rasters:
        raise FileNotFoundError(f"No hay rasters MapBiomas en {directorio}.")
    return rasters
