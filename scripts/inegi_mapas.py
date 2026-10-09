"""
    Gestor de descarga de mapas del INEGI (https://www.inegi.org.mx/app/mapas/).

    Replica la consulta que realiza la aplicación web contra su API interna
    POST /app/api/productos/interna_v2/mapas/lista/resultados
    y localiza los productos:

    "Conjunto de datos vectoriales de uso del suelo y vegetación.
     Escala 1:250 000. Serie <I-VII>. Conjunto/Continuo Nacional"

    en formato SHP (el enlace apunta a un .zip que contiene el shapefile).
"""

from pathlib import Path
import re
import sys
import time
import zipfile

import requests as r
from yarl import URL

from scripts.config import DATA_DIR

HOST = URL("https://www.inegi.org.mx")
API = HOST / "app" / "api" / "productos" / "interna_v2" / "mapas"

# Códigos de filtro de la API (obtenidos de /combos?opt=<api>):
#   esca = 2  -> escala 1:250 000
#   form = 9  -> formato SHP
#   tipoB = 1 -> buscar frase completa ; tipoB = 2 -> cualquier palabra
CONSULTA_BASE = {
    "enti": "", "muni": "", "loca": "", "tema": "", "titg": "",
    "esca": 2, "edic": "", "form": 9, "prog": "",
    "busc": "uso del suelo y vegetación",
    "tipoB": 1, "adv": False, "rango": "", "sens": "", "uedo": "",
    "reso": "", "point": "", "malla": "", "poligono": "", "buscAG": None,
    "orden": 4, "desc": True, "pag": 0, "tam": 100,
}

SERIES = ("I", "II", "III", "IV", "V", "VI", "VII")

# Título nacional: "... Serie <romano>. Conjunto|Continuo Nacional [.]"
PATRON_NACIONAL = re.compile(
    r"[Ss]erie\s*\(?([IVX]+)\)?\s*\.?\s*(Conjunto|Continuo)\s+Nacional\.?\s*$"
)

SESION = r.Session()
SESION.headers.update({"User-Agent": "Mozilla/5.0"})


def _post(endpoint: str, payload: dict, intentos: int = 4) -> dict:
    """POST a la API con reintentos ante fallos transitorios."""
    url = str(API / endpoint)
    for n in range(intentos):
        try:
            resp = SESION.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except r.RequestException:
            if n == intentos - 1:
                raise
            time.sleep(2 * (n + 1))


def buscar_mapas(consulta: dict = CONSULTA_BASE) -> list[dict]:
    """Recorre todas las páginas de resultados de la consulta dada."""
    mapas, pagina = [], 0
    while True:
        consulta["pag"] = pagina
        datos = _post("lista/resultados", consulta)
        if not datos.get("success"):
            raise RuntimeError(f"La API rechazó la consulta: {datos}")
        lote = datos["list"]["mapas"]
        if not lote:
            break
        mapas.extend(lote)
        if len(lote) < consulta["tam"]:
            break
        pagina += 1
    return mapas


def catalogo_nacional(consulta: dict = CONSULTA_BASE) -> dict[str, dict]:
    """
        Del resultado de la búsqueda conserva sólo el producto nacional
        de cada serie. El catálogo contiene registros homónimos por
        entidad federativa, por lo que además del patrón del título se
        exige entidad == 'Estados Unidos Mexicanos'.

        return: {"I": {"key", "titulo", "edicion", "url", "peso"}, ...}
    """
    catalogo = {}
    for mapa in buscar_mapas(consulta):
        titulo = mapa.get("titulo", "").strip()
        coincide = PATRON_NACIONAL.search(titulo)
        if not coincide or mapa.get("entidad") != "Estados Unidos Mexicanos":
            continue
        shp = next(
            (f for f in mapa.get("formatos", []) if f.get("extension") == "SHP"),
            None,
        )
        if shp is None:
            continue
        catalogo[coincide.group(1)] = {
            "key": mapa["key"],
            "titulo": titulo,
            "edicion": mapa.get("edicion"),
            "url": str(HOST / shp["url"]["valor"].lstrip("/")),
            "peso": shp.get("peso"),
        }
    return catalogo


def descargar(url: str, destino: Path, intentos: int = 4) -> Path:
    """Descarga en flujo a `destino` (no repite si el archivo ya existe)."""
    if destino.exists():
        print(f"  Ya existe: {destino.name}")
        return destino
    temporal = destino.with_suffix(destino.suffix + ".part")
    for n in range(intentos):
        try:
            with SESION.get(url, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", 0))
                recibido = 0
                with open(temporal, "wb") as f:
                    for bloque in resp.iter_content(chunk_size=1 << 20):
                        f.write(bloque)
                        recibido += len(bloque)
                        if total:
                            print(
                                f"\r  {destino.name}: "
                                f"{recibido / 2**20:.0f}/{total / 2**20:.0f} MB",
                                end="", flush=True,
                            )
            print()
            temporal.rename(destino)
            return destino
        except r.RequestException as e:
            print(f"\n  Reintento {n + 1}/{intentos} por: {e}")
            time.sleep(2 * (n + 1))
    raise RuntimeError(f"No se pudo descargar {url}")


def descargar_series(
    series: tuple[str, ...] = SERIES, extraer: bool = False
) -> dict[str, Path]:
    """
        Descarga los zips SHP de las series indicadas a data/pure/INEGI/.

        pars:
            series: subconjunto de SERIES, p. ej. ("VII",).
            extraer: si True, descomprime cada zip junto al archivo.
        return: {"I": Path, "II": Path, ...}
    """
    catalogo = catalogo_nacional()
    destino_dir = DATA_DIR / "pure" / "INEGI"
    destino_dir.mkdir(parents=True, exist_ok=True)
    rutas = {}
    for serie in series:
        if serie not in catalogo:
            print(f"Serie {serie}: no localizada en el catálogo")
            continue
        info = catalogo[serie]
        nombre = f"usv_250k_serie_{serie}_{info['key']}.zip"
        print(f"Serie {serie} ({info['edicion']}): {info['titulo'][:70]}...")
        rutas[serie] = descargar(info["url"], destino_dir / nombre)
        if extraer:
            with zipfile.ZipFile(rutas[serie]) as z:
                z.extractall(rutas[serie].with_suffix(""))
    return rutas


if __name__ == "__main__":
    """
        Uso:
            python -m scripts.inegi_mapas            # sólo lista el catálogo
            python -m scripts.inegi_mapas VII        # descarga la serie VII
            python -m scripts.inegi_mapas all        # descarga I-VII (~4.5 GB)
            python -m scripts.inegi_mapas all -x     # descarga y descomprime
    """
    args = [a for a in sys.argv[1:] if a != "-x"]
    extraer = "-x" in sys.argv
    if not args:
        for serie, info in sorted(
            catalogo_nacional().items(), key=lambda kv: SERIES.index(kv[0])
        ):
            print(f"Serie {serie} (ed. {info['edicion']})")
            print(f"  {info['titulo']}")
            print(f"  {info['url']}")
    else:
        elegidas = SERIES if args[0] == "all" else tuple(
            s.upper() for s in args if s.upper() in SERIES
        )
        descargar_series(elegidas, extraer)
