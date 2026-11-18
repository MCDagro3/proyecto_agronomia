"""
    Extracción masiva de parámetros climáticos de NASA POWER para México.

    Fuente: datamart público en AWS S3 (Registry of Open Data), stores Zarr
    del Analysis Ready Datastore (ARD). No usa la API REST: los stores
    remotos se leen con zarr/fsspec y sólo se descargan los chunks que
    cubren el bbox de México y los años objetivo.

    Mapeo serie USyV -> año (ver docs/metodologia_usv_inegi_mapbiomas.md):
        I->1981 (POWER inicia en 1981; la serie es ~1980),
        II->1985, III->1993, IV->2002, V->2007, VI->2015, VII->2018.

    Disponibilidad por fuente:
        merra2   : diario 1981-01-01 -> ~2029 (grilla 0.5 x 0.625 grados)
        syn1deg  : diario 2001-01-01 -> ~2029 (grilla 1 x 1 grado)
        srb      : diario 1984+ (sin DIRH/UV_INDEX/PSH; no usado)
        imerg    : diario 0.1 grados, sólo UTC (excluido por peso/resolución)

    Uso:
        python -m scripts.nasa_power            # descarga todo el subset
        python -m scripts.nasa_power T2M PW     # sólo algunos parámetros
"""

import datetime as dt
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

import fsspec
import numpy as np
import pandas as pd
import zarr

from scripts.config import DATA_DIR

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

BASE_S3 = "https://nasa-power.s3.us-west-2.amazonaws.com"
# El .ods vive en la raíz de data/ (no dentro de una etapa pure/raw/...).
ODS_PARAMETROS = DATA_DIR / "nasa-power-parameters.ods"

OUT_DIR = DATA_DIR / "interm" / "NASA"

# Serie USyV -> año representativo (mapeo del doc de metodología).
SERIES_ANIOS = {
    "I": 1981,   # serie ~1980; 1981 es el primer año con POWER
    "II": 1985,
    "III": 1993,
    "IV": 2002,
    "V": 2007,
    "VI": 2015,
    "VII": 2018,
}

# Bbox continental de México (WGS84, grados). La malla nativa del store
# recorta a sus celdas; se amplía media celda para no perder bordes.
BBOX = {"lat_min": 14.0, "lat_max": 33.0, "lon_min": -119.0, "lon_max": -86.0}

# Subset agrícola del .ods: parámetro -> store Zarr (temporal/daily/LST).
PARAMETROS_AGRICOLAS = {
    # MERRA-2 (1981+), grilla 0.5 x 0.625
    "T2M": "merra2",
    "T2M_MAX": "merra2",
    "T2M_MIN": "merra2",
    "PRECTOTCORR": "merra2",
    "GWETROOT": "merra2",
    "EVPTRNS": "merra2",
    "TSURF": "merra2",
    "FROST_DAYS": "merra2",
    "CDD0": "merra2",
    "HDD0": "merra2",
    # CERES SYN1deg (2001+), grilla 1 x 1 -> sólo series IV-VII
    "PW": "syn1deg",
    "ALLSKY_SFC_UV_INDEX": "syn1deg",
    "ALLSKY_SFC_SW_DIRH": "syn1deg",
    "PSH": "syn1deg",
}

STORES = {
    name: (
        f"{BASE_S3}/{name}/temporal/"
        f"power_{name}_daily_temporal_lst.zarr"
    )
    for name in ("merra2", "syn1deg", "srb", "geosit")
}
# imerg sólo existe en UTC:
STORES["imerg"] = f"{BASE_S3}/imerg/temporal/power_imerg_daily_temporal_utc.zarr"


# ---------------------------------------------------------------------------
# Lectura del .ods (stdlib, sin odfpy)
# ---------------------------------------------------------------------------

def parsear_parametros(ruta: Path = ODS_PARAMETROS) -> pd.DataFrame:
    """
        Extrae el diccionario de parámetros del .ods.

        return: DataFrame[code, name, description, keywords]
    """
    T = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
    X = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
    with zipfile.ZipFile(ruta) as z:
        root = ET.fromstring(z.read("content.xml"))
    tabla = next(root.iter(T + "table"))
    filas = []
    for row in tabla.iter(T + "table-row"):
        celdas = [
            "".join(p.text or "" for p in c.iter(X + "p")).strip()
            for c in row
        ]
        if celdas and celdas[0]:
            filas.append(celdas[:5] + [""] * (5 - len(celdas)))
    return pd.DataFrame(
        filas, columns=["code", "name", "description", "kw1", "kw2"]
    )


# ---------------------------------------------------------------------------
# Acceso a los stores Zarr remotos
# ---------------------------------------------------------------------------

def _grupo(store: str):
    return zarr.open_group(fsspec.get_mapper(STORES[store]), mode="r")


def _epocho(store: str) -> dt.date:
    """Fecha base del eje temporal ('days since YYYY-MM-DD ...')."""
    g = _grupo(store)
    unidades = g["time"].attrs["units"]
    m = re.search(r"days since (\d{4}-\d{2}-\d{2})", unidades)
    return dt.date.fromisoformat(m.group(1))


def _indices_anio(store: str, anio: int) -> tuple[int, int] | None:
    """Rango [i0, i1) de días del año indicado; None si fuera de cobertura."""
    g = _grupo(store)
    n = len(g["time"][:])
    ep = _epocho(store)
    i0 = (dt.date(anio, 1, 1) - ep).days
    i1 = (dt.date(anio + 1, 1, 1) - ep).days
    if i0 < 0 or i1 > n or i0 >= i1:
        return None
    return i0, i1


def anios_disponibles(param: str) -> dict[str, int]:
    """Serie -> año realmente disponible para el parámetro en su store."""
    store = PARAMETROS_AGRICOLAS[param]
    out = {}
    for serie, anio in SERIES_ANIOS.items():
        if _indices_anio(store, anio) is not None:
            out[serie] = anio
    return out


# ---------------------------------------------------------------------------
# Descarga y guardado
# ---------------------------------------------------------------------------

def extraer_parametro(param: str) -> dict[str, pd.DataFrame]:
    """
        Descarga el parámetro para México en los años de cada serie.

        return: {"I": DataFrame, ...} sólo con las series disponibles.
        Cada DataFrame está en formato largo:
            time (date32), lat, lon, value, param, units
    """
    store = PARAMETROS_AGRICOLAS[param]
    g = _grupo(store)
    ep = _epocho(store)
    a = g[param]
    units = a.attrs.get("units", "")

    lat = g["lat"][:]
    lon = g["lon"][:]
    if lat[0] > lat[-1]:
        lat = lat[::-1]
    iy0 = int(np.searchsorted(lat, BBOX["lat_min"], "left"))
    iy1 = int(np.searchsorted(lat, BBOX["lat_max"], "right"))
    ix0 = int(np.searchsorted(lon, BBOX["lon_min"], "left"))
    ix1 = int(np.searchsorted(lon, BBOX["lon_max"], "right"))
    lat_s, lon_s = lat[iy0:iy1], lon[ix0:ix1]

    resultado = {}
    for serie, anio in SERIES_ANIOS.items():
        rango = _indices_anio(store, anio)
        if rango is None:
            continue
        t0, t1 = rango
        datos = np.asarray(a[t0:t1, iy0:iy1, ix0:ix1])  # (dias, lat, lon)
        fechas = [ep + dt.timedelta(days=int(d))
                  for d in range(t0, t1)]
        # long format: una fila por (fecha, celda)
        mesh_t, mesh_y, mesh_x = np.meshgrid(
            np.arange(len(fechas)),
            np.arange(len(lat_s)),
            np.arange(len(lon_s)),
            indexing="ij",
        )
        df = pd.DataFrame({
            "time": pd.to_datetime(fechas)[mesh_t.ravel()],
            "lat": lat_s[mesh_y.ravel()],
            "lon": lon_s[mesh_x.ravel()],
            "value": datos.ravel(),
            "param": param,
            "units": units,
            "serie": serie,
        })
        resultado[serie] = df
        print(f"  {param} serie {serie} ({anio}): "
              f"{len(df):,} filas, "
              f"{len(lat_s)}x{len(lon_s)} celdas")
    return resultado


def guardar(param: str, out_dir: Path = OUT_DIR) -> list[Path]:
    """Extrae y escribe un parquet por serie disponible."""
    series = extraer_parametro(param)
    rutas = []
    for serie, df in series.items():
        destino = out_dir / f"serie_{serie}" / f"{param}.parquet"
        destino.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(destino, index=False)
        rutas.append(destino)
        print(f"    -> {destino.relative_to(DATA_DIR.parent)}")
    return rutas


def descargar_subset(
    params: list[str] | None = None, out_dir: Path = OUT_DIR
) -> pd.DataFrame:
    """Descarga todos los parámetros del subset y devuelve el catálogo."""
    params = params or list(PARAMETROS_AGRICOLAS)
    out_dir.mkdir(parents=True, exist_ok=True)
    catalogo = parsear_parametros()
    meta = catalogo[catalogo["code"].isin(PARAMETROS_AGRICOLAS)].copy()
    meta["store"] = meta["code"].map(PARAMETROS_AGRICOLAS)
    meta["anios"] = meta["code"].map(
        lambda p: ",".join(f"{s}:{y}" for s, y in anios_disponibles(p).items())
    )
    for param in params:
        print(f"Parámetro {param} ({PARAMETROS_AGRICOLAS[param]}):")
        guardar(param, out_dir)
    meta.to_csv(out_dir / "catalogo_parametros.csv", index=False)
    return meta


if __name__ == "__main__":
    seleccion = sys.argv[1:] or list(PARAMETROS_AGRICOLAS)
    desconocidos = [p for p in seleccion if p not in PARAMETROS_AGRICOLAS]
    if desconocidos:
        sys.exit(f"Parámetros fuera del subset: {desconocidos}")
    descargar_subset(seleccion)
