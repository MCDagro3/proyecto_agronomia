from functools import cached_property
from io import StringIO
from pathlib import Path
import random
import re
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from loguru import logger
import pandas as pd
import requests
from tqdm import tqdm

from proyecto_agronomia.config import (
    AGRICULTURA_DICCIONARIO_PATH,
    AGRICULTURA_DICCIONARIO_URL,
    AGRICULTURA_RAW_DIR,
    AGRICULTURA_URL_TEMPLATE,
    DGSIAP_AGROPROGRAMA_RAW_DIR,
    DGSIAP_AGROPROGRAMA_URL,
    DGSIAP_AVANCE_RAW_DIR,
    DGSIAP_AVANCE_URL,
    DGSIAP_DATOS_ABIERTOS_URL,
)

TIPO_REPORTE = {"geografico": 1, "cultivo": 2}
NIVEL_REPORTE = {
    "entidad": 2,
    "distrito_municipio": 3,
    "distrito": 0,
    "municipio": 1,
}
CLAVES_AGROPROGRAMA = ("CVEGEO", "Clave Entidad", "Clave Municipio")
ALIAS_CULTIVOS = {"alfalfa": "alfalfa verde"}


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
            respuesta = requests.get(
                url,
                timeout=120,
            )
            respuesta.raise_for_status()

            ruta.write_bytes(respuesta.content)

        except requests.RequestException as error:
            logger.error(f"[{anio}] Error durante la descarga: {error}")
            continue

        logger.success(f"[{anio}] Descargado ({ruta.stat().st_size / (1024**2):.2f} MB)")

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
        logger.info("El diccionario agrícola ya existe.")
        return ruta

    logger.info("Descargando diccionario agrícola DGSIAP...")

    try:
        respuesta = requests.get(
            AGRICULTURA_DICCIONARIO_URL,
            timeout=120,
        )

        respuesta.raise_for_status()

        ruta.write_bytes(respuesta.content)

    except requests.RequestException as error:
        logger.error(f"Error descargando el diccionario agrícola: {error}")
        raise

    logger.success(f"Diccionario agrícola descargado: {ruta.name}")

    return ruta


def descubrir_recursos_dgsiap(
    url: str = DGSIAP_DATOS_ABIERTOS_URL,
    timeout: int = 120,
    sesion: requests.Session | None = None,
) -> dict[str, dict]:
    """Descubre diccionarios, metadatos y archivos históricos de DGSIAP.

    La consulta se realiza únicamente al invocar la función. El resultado
    conserva las URLs publicadas por el portal y no descarga los archivos.
    """
    cliente = sesion or requests.Session()
    respuesta = cliente.get(url, timeout=timeout)
    respuesta.raise_for_status()

    pagina = BeautifulSoup(respuesta.content, "lxml")
    principal = pagina.find("main")
    if principal is None:
        raise RuntimeError("DGSIAP cambió su página: no se encontró <main>.")
    secciones = principal.find_all("section", recursive=False)
    if len(secciones) < 4:
        raise RuntimeError("DGSIAP cambió su página: faltan secciones esperadas.")

    historico = secciones[3].find("div", {"id": "dataAccordion"})
    if historico is None:
        raise RuntimeError("No se encontró el catálogo histórico de DGSIAP.")
    bloques = {
        bloque.find("div", {"class": "d-flex align-items-center"}).get_text(
            " ", strip=True
        ): bloque
        for bloque in historico.find_all("div", recursive=False)
        if bloque.find("div", {"class": "d-flex align-items-center"})
    }

    recursos: dict[str, dict] = {}
    for categoria, bloque in bloques.items():
        seccion_diccionario = (
            secciones[2].find("div", {"class": "dict-section"})
            if categoria == "Municipal"
            else bloque
        )
        columnas = seccion_diccionario.find_all("div", {"class": re.compile(r"col-12 col-md-6.*")})
        if len(columnas) < 2:
            logger.warning(f"DGSIAP: se omitió la categoría {categoria!r}.")
            continue
        diccionario, metadatos = columnas[0], columnas[1]
        enlace = diccionario.find("a", href=True)
        detalle = metadatos.find("div")
        valores = detalle.find_all("div", recursive=False) if detalle else []
        recursos[categoria] = {
            "diccionario": {
                "titulo": diccionario.find("h2").get_text(" ", strip=True),
                "descripcion": diccionario.find("p").get_text(" ", strip=True),
                "url": enlace["href"] if enlace else None,
            },
            "metadatos": {
                "titulo": detalle.find("h4").get_text(" ", strip=True)
                if detalle and detalle.find("h4")
                else None,
                "estado": valores[0].get_text(" ", strip=True) if valores else None,
                "rango": valores[1].get_text(" ", strip=True) if len(valores) > 1 else None,
            },
            "datasets": [
                enlace["href"] for enlace in bloque.find_all("a", {"class": "dl-btn"}, href=True)
            ],
        }
    return recursos


class AvanceAgricola:
    """Cliente del Avance de Siembras y Cosechas de DGSIAP."""

    def __init__(self, timeout: int = 120, sesion: requests.Session | None = None):
        self.session = sesion or requests.Session()
        self.timeout = timeout

    def _xajax(self, funcion: str, *args) -> dict[str, str]:
        respuesta = self.session.get(
            DGSIAP_AVANCE_URL,
            timeout=self.timeout,
            params={
                "xajax": funcion,
                "xajaxr": 1,
                "xajaxargs[]": [str(argumento) for argumento in args],
            },
        )
        respuesta.raise_for_status()
        texto = respuesta.content.decode("cp1252", errors="replace")
        previo, _, xml = texto.partition("<xjx>")
        try:
            comandos = ET.fromstring("<xjx>" + xml) if xml else []
        except ET.ParseError as error:
            raise RuntimeError(f"Respuesta xajax inválida para {funcion}.") from error
        salida = {
            comando.get("t"): comando.text
            for comando in comandos
            if comando.get("n") == "as" and (comando.text or "").strip()
        }
        if not salida:
            mensaje = BeautifulSoup(previo, "html.parser").get_text(" ", strip=True)
            raise RuntimeError(f"{funcion}{args}: sin datos. {mensaje}")
        return salida

    def _opciones(self, funcion: str, *args) -> dict[str, str]:
        html = next(iter(self._xajax(funcion, *args).values()))
        pagina = BeautifulSoup(html, "html.parser")
        return {
            opcion.get("value", ""): opcion.get_text(strip=True)
            for opcion in pagina.find_all("option")
        }

    def anios(self):
        return self._opciones("llenaAnios")

    def meses(self, anio):
        return self._opciones("llenaMes", anio)

    def ciclos(self):
        return self._opciones("llenaCiclo")

    def modalidades(self):
        return self._opciones("llenaModa")

    def entidades(self):
        return self._opciones("llenaEntidades")

    def distritos(self, entidad):
        return self._opciones("llenaDistrito", entidad)

    def municipios(self, entidad, distrito=0):
        return self._opciones("cargaMuni", entidad, distrito)

    def cultivos(self, anio, mes, ciclo=5, entidad=0, distrito=0, municipio=0):
        return self._opciones("llenaCultivo", anio, entidad, mes, ciclo, distrito, municipio)

    def unidades(self, cultivo):
        return self._opciones("llenaUnidMed", cultivo)

    def variedades(self, cultivo, unidad=None):
        unidad = unidad or next(iter(self.unidades(cultivo)))
        return self._opciones("llenaVariedad", cultivo, unidad)

    def reporte(
        self,
        anio=0,
        mes=0,
        ciclo=5,
        modalidad=3,
        entidad=0,
        distrito=0,
        municipio=0,
        cultivo=0,
        variedad=0,
        nivel="entidad",
        tipo="geografico",
    ) -> pd.DataFrame:
        """Consulta el avance agrícola y devuelve la tabla publicada."""
        if nivel not in NIVEL_REPORTE or tipo not in TIPO_REPORTE:
            raise ValueError("Revisa los valores de nivel y tipo.")
        html = self._xajax(
            "reporte",
            TIPO_REPORTE[tipo],
            anio,
            ciclo,
            modalidad,
            entidad,
            distrito,
            municipio,
            cultivo,
            0,
            variedad,
            NIVEL_REPORTE[nivel],
            0,
            0,
            0,
            mes,
        ).get("Resultado")
        if not html:
            raise RuntimeError("DGSIAP no devolvió el elemento Resultado.")
        tabla = pd.read_html(StringIO(html), thousands=",")[0]
        tabla.columns = [
            inferior if not str(inferior).startswith("Unnamed") else superior
            for superior, inferior in tabla.columns
        ]
        tabla = tabla.iloc[:, 1:]
        tabla = tabla[tabla.iloc[:, 0] != "Total"].reset_index(drop=True)
        titulo = BeautifulSoup(html, "html.parser").select_one(".titulosTabla")
        tabla.attrs["encabezado"] = titulo.get_text(" ", strip=True) if titulo else None
        return tabla


class AgroPrograma:
    """Cliente de intención de siembra y cosecha de DGSIAP."""

    def __init__(self, timeout: int = 120, sesion: requests.Session | None = None):
        self.session = sesion or requests.Session()
        self.timeout = timeout
        self.control_url = (
            f"{DGSIAP_AGROPROGRAMA_URL.rstrip('/')}/control/ctrl.siembras.cosechas.php"
        )

    @cached_property
    def tokens(self) -> dict[str, str]:
        respuesta = self.session.get(DGSIAP_AGROPROGRAMA_URL, timeout=self.timeout)
        respuesta.raise_for_status()
        pagina = BeautifulSoup(respuesta.text, "html.parser")
        tokens = {
            elemento["id"]: elemento["data-verificacion"]
            for elemento in pagina.select("[data-verificacion]")
        }
        for elemento in pagina.select("#reporteInit, #cargaUM, #cargaVar"):
            tokens[elemento["id"]] = elemento["value"]
        return tokens

    def _post(self, accion: str, **parametros) -> requests.Response:
        if accion not in self.tokens:
            raise KeyError(f"No se encontró el token para {accion!r}.")
        respuesta = self.session.post(
            self.control_url,
            timeout=self.timeout,
            data={
                "action": self.tokens[accion],
                "rnd": random.randrange(10_000),
                **parametros,
            },
        )
        respuesta.raise_for_status()
        if not respuesta.text.strip():
            raise RuntimeError(f"{accion}{parametros}: respuesta vacía.")
        return respuesta

    def _opciones(self, accion: str, **parametros) -> dict[str, str]:
        return {
            str(opcion["ID"]): opcion["NOMBRE"].strip()
            for opcion in self._post(accion, **parametros).json()
        }

    def anios(self):
        return self._opciones("anioagric", CLAVE=1)

    def ciclos(self):
        return self._opciones("cicloProd", CLAVE=1)

    def modalidades(self):
        return self._opciones("modalidad", CLAVE=1)

    def entidades(self):
        return self._opciones("entidad", CLAVE=1)

    def distritos(self, entidad):
        return self._opciones("distrito", estado=entidad)

    def municipios(self, entidad, distrito=0):
        return self._opciones("municipio", estado=entidad, distrito=distrito)

    def cultivos(self, anio, ciclo=5, entidad=0):
        return self._opciones("cultivo", anio=anio, edo=entidad, ciclo=ciclo)

    def unidades(self, cultivo):
        return self._opciones("cargaUM", cultivo=cultivo)

    def variedades(self, cultivo, unidad=None):
        unidad = unidad or next(iter(self.unidades(cultivo)))
        return self._opciones("cargaVar", cultivo=cultivo, unidMedida=unidad)

    def anio_vigente(self) -> int:
        return int(self._post("reporteInit", VAL=1).json()["ANIO_AGRICOLA"])

    def reporte(
        self,
        anio=0,
        ciclo=5,
        modalidad=3,
        entidad=0,
        distrito=0,
        municipio=0,
        cultivo=0,
        variedad=0,
        nivel="entidad",
        tipo="geografico",
    ) -> pd.DataFrame:
        """Consulta la intención de siembra y devuelve la tabla publicada."""
        if nivel not in NIVEL_REPORTE or tipo not in TIPO_REPORTE:
            raise ValueError("Revisa los valores de nivel y tipo.")
        html = self._post(
            "Consultar",
            tipo=TIPO_REPORTE[tipo],
            anioagric=anio or self.anio_vigente(),
            cicloProd=ciclo,
            modalidad=modalidad,
            entidad=entidad,
            distrito=distrito,
            municipio=municipio,
            cultivo=cultivo,
            unidMed=0,
            variedad=variedad,
            opcionDDRMpio=NIVEL_REPORTE[nivel],
        ).text
        pagina = BeautifulSoup(html, "html.parser")
        if pagina.table is None:
            raise RuntimeError(f"Reporte sin datos: {pagina.get_text(' ', strip=True)}")
        tabla = pd.read_html(
            StringIO(html),
            thousands=",",
            converters=dict.fromkeys(CLAVES_AGROPROGRAMA, str),
        )[0]
        tabla = tabla[tabla["No."] != "Total"].drop(columns="No.").reset_index(drop=True)
        tabla.attrs["encabezado"] = " ".join(
            elemento.get_text(" ", strip=True)
            for elemento in pagina.select("#subTitleMod, #titulosFiltros")
        )
        return tabla


def normalizar_nombre_cultivo_catalogo(nombre: str) -> str:
    """Normaliza nombres para vincular catálogos de los portales DGSIAP."""
    base = re.sub(r"\s*\(.*?\)", "", nombre.lower())
    base = " ".join(base.replace(" en verde", " verde").split())
    return ALIAS_CULTIVOS.get(base, base)


def equivalencia_cultivos(anio: int, ciclo: int = 5) -> pd.DataFrame:
    """Relaciona por nombre los identificadores de AgroPrograma y Avance."""
    catalogos = {
        "agroprograma": AgroPrograma().cultivos(anio, ciclo),
        "avance": AvanceAgricola().cultivos(anio, 0, ciclo),
    }
    tablas = [
        pd.DataFrame(
            [
                (normalizar_nombre_cultivo_catalogo(nombre), clave, nombre)
                for clave, nombre in cultivos.items()
                if clave != "0"
            ],
            columns=["base", f"id_{sitio}", f"cultivo_{sitio}"],
        )
        for sitio, cultivos in catalogos.items()
    ]
    return tablas[0].merge(tablas[1], on="base", how="outer").drop(columns="base")


def descargar_reporte_avance(
    ruta: Path | None = None,
    **filtros,
) -> Path:
    """Consulta y guarda un reporte de avance agrícola dentro de ``data/raw``."""
    tabla = AvanceAgricola().reporte(**filtros)
    anio = filtros.get("anio", 0) or "vigente"
    ruta = ruta or DGSIAP_AVANCE_RAW_DIR / f"avance_agricola_{anio}.csv"
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(ruta, index=False, encoding="utf-8")
    encabezado = tabla.attrs.get("encabezado")
    if encabezado:
        ruta.with_suffix(".metadata.txt").write_text(encabezado, encoding="utf-8")
    return ruta


def descargar_reporte_agroprograma(
    ruta: Path | None = None,
    **filtros,
) -> Path:
    """Consulta y guarda intención de siembra dentro de ``data/raw``."""
    cliente = AgroPrograma()
    tabla = cliente.reporte(**filtros)
    anio = filtros.get("anio", 0) or cliente.anio_vigente()
    ruta = ruta or DGSIAP_AGROPROGRAMA_RAW_DIR / f"agroprograma_{anio}.csv"
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(ruta, index=False, encoding="utf-8")
    encabezado = tabla.attrs.get("encabezado")
    if encabezado:
        ruta.with_suffix(".metadata.txt").write_text(encabezado, encoding="utf-8")
    return ruta
