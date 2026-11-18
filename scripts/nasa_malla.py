"""
    Malla de puntos agrícolas de México con anotación climática NASA POWER.

    Construye una malla regular en EPSG:6372 sobre las zonas agrícolas de las
    7 series USyV del INEGI y conserva las celdas que son >= UMBRAL_AG
    agrícolas en TODAS las series (intersección persistente, filtrada de
    forma iterativa serie por serie). Cada celda superviviente genera un
    punto en el centroide de su agricultura (máscara de la Serie VII).

    Cada punto se anota con las features climáticas anuales de NASA POWER
    (parquets diarios en data/interm/NASA/serie_{S}/, generados por
    scripts/nasa_power.py):

    - celda merra2 (0.5 x 0.625 grados) y celda syn1deg (1 x 1 grado);
    - firma climática = promedio entre las 7 series de cada agregado anual;
    - zona_clima (KMeans sobre features estandarizadas);
    - flags de extremos climáticos (deciles de aridez, T2M, precipitación,
      heladas) y de redundancia (varios puntos en la misma celda POWER).

    Uso:
        python -m scripts.nasa_malla            # flujo completo
        python -m scripts.nasa_malla fracciones # solo máscaras por serie
"""

from pathlib import Path
import sys
import unicodedata
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
import shapely
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from scripts.config import DATA_DIR

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

PURE = DATA_DIR / "pure" / "INEGI"
USV_DIR = DATA_DIR / "raw" / "INEGI" / "usv"
MARCO = DATA_DIR / "raw" / "INEGI" / "Mexico" / "conjunto_de_datos"
NASA_DIR = DATA_DIR / "interm" / "NASA"
OUT_DIR = DATA_DIR / "process" / "NASA"

CRS_TRABAJO = "EPSG:6372"
CRS_SALIDA = "EPSG:4326"
LCC_INEGI = (
    "+proj=lcc +ellps=GRS80 +lat_0=12 +lon_0=-102 +lat_1=17.5 +lat_2=29.5 "
    "+x_0=2500000 +y_0=0 +units=m +no_defs"
)

GRID_M = 5000            # lado de la celda de la malla (m)
SUBPIXEL = 5             # subpíxeles por celda -> resolución GRID_M/SUBPIXEL
UMBRALES = {s: 0.5 for s in ("I", "II", "III", "IV", "V", "VI", "VII")}
K_ZONAS = 10
SEMILLA = 2026
Q_EXTREMO = 0.10         # cuantil para marcar climas extremos

SERIES_ANIO = {"I": 1980, "II": 1993, "III": 2002, "IV": 2007,
               "V": 2011, "VI": 2014, "VII": 2018}
SERIES = list(SERIES_ANIO)

BASE_SHP = {
    "I": "us250s1v_lcc", "II": "us250s2v_lcc", "III": "us250s3g",
    "IV": "us250s4g", "V": "usv250s5g", "VI": "usv250s6_union",
    "VII": "cdv_usuev250sVII_cnal",
}
ZIP_POR_SERIE = {
    "I": "usv_250k_serie_I_702825007020.zip",
    "II": "usv_250k_serie_II_702825007021.zip",
    "III": "usv_250k_serie_III_702825007022.zip",
    "IV": "usv_250k_serie_IV_702825007023.zip",
    "V": "usv_250k_serie_V_702825007024.zip",
    "VI": "usv_250k_serie_VI_889463598459.zip",
    "VII": "usv_250k_serie_VII_889463842781.zip",
}

ESQUEMA = {
    "I": {"tipo": "s12", "encoding": "ISO-8859-1"},
    "II": {"tipo": "s12"},
    "III": {"tipo": "g", "clave": "CLAVE"},
    "IV": {"tipo": "g", "clave": "CVE_G"},
    "V": {"tipo": "g", "clave": "CVE_G"},
    "VI": {"tipo": "union", "clave": "CVE_UNION"},
    "VII": {"tipo": "union", "clave": "CLAVE"},
}

CICLOS = {"ANUAL": "A", "SEMIPERMANENTE": "S", "PERMANENTE": "P"}
REGIMENES = {"RIEGO": "R", "RIEGO EVENTUAL": "R",
             "TEMPORAL": "T", "HUMEDAD": "H"}
ORDEN_CICLO = "ASP"
CICLOS_VALIDOS = ["A", "S", "P", "AS", "AP", "SP"]
CLASES = [r + c for r in "TRH" for c in CICLOS_VALIDOS]
NOMBRE_REGIMEN = {"R": "RIEGO", "T": "TEMPORAL", "H": "HUMEDAD"}
NOMBRE_CICLO = {"A": "ANUAL", "S": "SEMIPERMANENTE", "P": "PERMANENTE"}
DESCRIPCION = {
    r + c: f"AGRICULTURA DE {NOMBRE_REGIMEN[r]} "
           + " Y ".join(NOMBRE_CICLO[x] for x in c)
    for r in "TRH" for c in CICLOS_VALIDOS
}

# POWER: suma anual vs media diaria; y store de cada parámetro
PARAM_SUM = {"PRECTOTCORR", "FROST_DAYS", "CDD0", "HDD0"}
SYN1DEG = {"PW", "ALLSKY_SFC_UV_INDEX", "ALLSKY_SFC_SW_DIRH", "PSH"}
PARAM_MEDIA = {"T2M", "T2M_MAX", "T2M_MIN", "GWETROOT", "EVPTRNS",
               "TSURF", "PW", "ALLSKY_SFC_UV_INDEX",
               "ALLSKY_SFC_SW_DIRH", "PSH"}
STORE_POR_PARAM = {p: ("syn1deg" if p in SYN1DEG else "merra2")
                   for p in PARAM_SUM | PARAM_MEDIA}
# W/m² de energía latente -> mm/día de ET (lambda = 2.45 MJ/kg)
LE_A_MM_DIA = 0.0353

# Columnas climáticas usadas para el clustering (firma merra2, prefijo m_)
CLIM_FEATURES = [f"m_clim_{p}" for p in (
    "T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "GWETROOT", "EVPTRNS",
    "TSURF", "FROST_DAYS", "CDD0", "HDD0")] + ["m_aridez", "m_gdd_anual"]
CLIM_EXTREMOS = ["m_aridez", "m_clim_T2M",
                 "m_clim_PRECTOTCORR", "m_clim_FROST_DAYS"]


def sin_acentos(texto):
    if not isinstance(texto, str):
        return texto
    t = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in t if not unicodedata.combining(ch)).upper().strip()


def normalizar(serie):
    return serie.map(sin_acentos)


def ciclo_canonico(c1, c2):
    presentes = {c for c in (c1, c2) if isinstance(c, str)}
    return "".join(c for c in ORDEN_CICLO if c in presentes)


# ---------------------------------------------------------------------------
# USyV: extracción, carga y fracción agrícola
# ---------------------------------------------------------------------------

def ruta_shp(serie: str) -> Path:
    return USV_DIR / f"serie_{serie}" / f"{BASE_SHP[serie]}.shp"


def extraer_zips() -> None:
    """Extrae de cada zip USyV sólo los archivos de la capa agrícola."""
    USV_DIR.mkdir(parents=True, exist_ok=True)
    for serie, zp in ZIP_POR_SERIE.items():
        shp = ruta_shp(serie)
        if shp.exists():
            continue
        destino = USV_DIR / f"serie_{serie}"
        destino.mkdir(parents=True, exist_ok=True)
        base = BASE_SHP[serie]
        with zipfile.ZipFile(PURE / zp) as z:
            for n in z.namelist():
                if Path(n).name.startswith(base) and not n.endswith("/"):
                    out = destino / Path(n).name
                    if not out.exists():
                        with z.open(n) as src, open(out, "wb") as dst:
                            while chunk := src.read(1 << 22):
                                dst.write(chunk)
        print(f"Serie {serie}: extraída en {destino}")


def _armonzar(gdf, serie, clave, regimen, c1, c2):
    out = gpd.GeoDataFrame(
        {"serie": serie, "clave_orig": clave.to_numpy(),
         "regimen": regimen.to_numpy(),
         "ciclo": [ciclo_canonico(a, b) for a, b in zip(c1, c2)]},
        geometry=gdf.geometry.to_numpy(), crs=gdf.crs,
    )
    out = out[out["regimen"].notna() & out["ciclo"].ne("")].copy()
    out["clase"] = out["regimen"] + out["ciclo"]
    return out.to_crs(CRS_TRABAJO).reset_index(drop=True)


def _cargar_s12(serie):
    enc = ESQUEMA[serie].get("encoding")
    gdf = gpd.read_file(ruta_shp(serie),
                        columns=["CLAVEFOT", "TIPO", "CULT_PRI", "CULT_SEC"],
                        encoding=enc)
    gdf = gdf.set_crs(LCC_INEGI, allow_override=True)
    regimen = normalizar(gdf["TIPO"]).map(REGIMENES)
    return _armonzar(gdf, serie, gdf["CLAVEFOT"], regimen,
                     normalizar(gdf["CULT_PRI"]).map(CICLOS),
                     normalizar(gdf["CULT_SEC"]).map(CICLOS))


def _cargar_g(serie):
    k = ESQUEMA[serie]["clave"]
    gdf = gpd.read_file(ruta_shp(serie),
                        columns=[k, "TIPAGES", "TIP_CUL1", "TIP_CUL2"])
    tipo = (normalizar(gdf["TIPAGES"])
            .str.extract(r"^AGRICULTURA DE (RIEGO|TEMPORAL|HUMEDAD)$")[0])
    return _armonzar(gdf, serie, gdf[k], tipo.map(REGIMENES),
                     normalizar(gdf["TIP_CUL1"]).map(CICLOS),
                     normalizar(gdf["TIP_CUL2"]).map(CICLOS))


def _cargar_union(serie):
    k = ESQUEMA[serie]["clave"]
    gdf = gpd.read_file(ruta_shp(serie), columns=[k, "DESCRIPCIO"])
    partes = normalizar(gdf["DESCRIPCIO"]).str.extract(
        r"^AGRICULTURA DE (RIEGO|TEMPORAL|HUMEDAD) (\w+)(?: Y (\w+))?$")
    return _armonzar(gdf, serie, gdf[k], partes[0].map(REGIMENES),
                     partes[1].map(CICLOS), partes[2].map(CICLOS))


CARGADORES = {"s12": _cargar_s12, "g": _cargar_g, "union": _cargar_union}
_CACHE_AGRI = NASA_DIR / "usv_agri"


def cargar_agricola(serie: str) -> gpd.GeoDataFrame:
    """Polígonos agrícolas (18 clases) de una serie en EPSG:6372."""
    cache = _CACHE_AGRI / f"usv_agri_{serie}.parquet"
    if cache.exists():
        return gpd.read_parquet(cache)
    cache.parent.mkdir(parents=True, exist_ok=True)
    gdf = CARGADORES[ESQUEMA[serie]["tipo"]](serie)
    assert set(gdf["clase"]) <= set(CLASES)
    gdf.to_parquet(cache)
    return gdf


# ---------------------------------------------------------------------------
# Malla regular y fracción agrícola
# ---------------------------------------------------------------------------

def bbox_mexico() -> tuple[float, float, float, float]:
    """(xmin, ymin, xmax, ymax) de México en EPSG:6372."""
    ent = gpd.read_file(MARCO / "00ent.shp").to_crs(CRS_TRABAJO)
    return tuple(ent.total_bounds)


def crear_malla(grid_m: int = GRID_M):
    """
        Rejilla regular sobre el bbox de México.

        return: (transform, shape, xs, ys) — transform/shape del raster de
        celdas; xs/ys = coordenadas de los centros de celda.
    """
    xmin, ymin, xmax, ymax = bbox_mexico()
    nx = int(np.ceil((xmax - xmin) / grid_m))
    ny = int(np.ceil((ymax - ymin) / grid_m))
    transform = from_origin(xmin, ymax, grid_m, grid_m)
    xs = xmin + (np.arange(nx) + 0.5) * grid_m
    ys = ymax - (np.arange(ny) + 0.5) * grid_m
    return transform, (ny, nx), xs, ys


def _raster_agricola(gdf, transform_sub, shape_sub):
    """Raster booleano de la unión de polígonos agrícolas (subpíxel)."""
    geoms = shapely.union_all(gdf.geometry.values)
    return rasterize(
        [(geoms, 1)], out_shape=shape_sub, transform=transform_sub,
        fill=0, dtype="uint8", all_touched=False,
    ).astype(bool)


def fraccion_agricola(serie: str, grid_m: int = GRID_M,
                      guardar: bool = True):
    """
        Fracción de cada celda cubierta por agricultura de la serie.

        return: (frac[ny,nx], info). info incluye transform, shape, xs, ys,
        grid_m y mask_sub (sólo para la Serie VII, para generar puntos).
    """
    cache = NASA_DIR / f"malla_frac_{serie}_{grid_m}.npz"
    transform, shape_cells, xs, ys = crear_malla(grid_m)
    ny_c, nx_c = shape_cells
    shape_sub = (ny_c * SUBPIXEL, nx_c * SUBPIXEL)
    transform_sub = rasterio.Affine(
        transform.a / SUBPIXEL, transform.b, transform.c,
        transform.d, transform.e / SUBPIXEL, transform.f)
    info = {"transform": transform, "shape": shape_cells,
            "xs": xs, "ys": ys, "grid_m": grid_m, "mask_sub": None}

    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        frac = z["frac"]
        if serie == "VII" and "mask_sub" in z.files:
            info["mask_sub"] = z["mask_sub"].astype(bool)
        return frac, info

    gdf = cargar_agricola(serie)
    mask_sub = _raster_agricola(gdf, transform_sub, shape_sub)
    bloques = mask_sub.reshape(ny_c, SUBPIXEL, nx_c, SUBPIXEL)
    frac = bloques.mean(axis=(1, 3))

    if guardar:
        datos = {"frac": frac, "xs": xs, "ys": ys,
                 "transform": np.array(transform)[:6], "grid_m": grid_m}
        if serie == "VII":
            datos["mask_sub"] = mask_sub.astype(np.uint8)
        np.savez_compressed(cache, **datos)
        info["mask_sub"] = mask_sub
    return frac, info


def filtro_iterativo(grid_m: int = GRID_M):
    """
        Aplica UMBRALES[serie] en cada serie, en orden I->VII.

        return: (mascara_final, embudo_df, info_vii)
    """
    mascara = np.ones(crear_malla(grid_m)[1], dtype=bool)
    embudo, info_vii = [], {}
    for serie in SERIES:
        frac, info = fraccion_agricola(serie, grid_m)
        mascara &= frac >= UMBRALES[serie]
        embudo.append({
            "serie": serie, "anio": SERIES_ANIO[serie],
            "umbral": UMBRALES[serie],
            "celdas_agricolas": int((frac >= UMBRALES[serie]).sum()),
            "celdas_supervivientes": int(mascara.sum()),
            "area_km2": round(mascara.sum() * grid_m**2 / 1e6, 1),
        })
        if serie == "VII":
            info_vii = info
    return mascara, pd.DataFrame(embudo), info_vii


# ---------------------------------------------------------------------------
# Puntos representativos por celda superviviente
# ---------------------------------------------------------------------------

def _centroides_celdas(mask_sub, mascara, info):
    """
        Centroide de los subpíxeles agrícolas (máscara VII) dentro de cada
        celda superviviente, vía summed-area tables. Celdas sin subpíxel
        agrícola caen al centro de la celda.

        return: (x, y, iy, ix) en EPSG:6372.
    """
    transform = info["transform"]
    ny, nx = mascara.shape
    mask = mask_sub[:ny * SUBPIXEL, :nx * SUBPIXEL].astype(np.float64)
    # Centro de cada subpíxel en coordenadas del raster
    cols, rows = np.meshgrid(np.arange(mask.shape[1]),
                             np.arange(mask.shape[0]))
    a_sub = transform.a / SUBPIXEL
    e_sub = transform.e / SUBPIXEL
    xs_sub = transform.c + (cols + 0.5) * a_sub
    ys_sub = transform.f + (rows + 0.5) * e_sub

    def sat(v):
        return np.pad(v.cumsum(0).cumsum(1), ((1, 0), (1, 0)))

    m = sat(mask)
    sx = sat(mask * xs_sub)
    sy = sat(mask * ys_sub)

    iy, ix = np.nonzero(mascara)
    i0, i1 = iy * SUBPIXEL, (iy + 1) * SUBPIXEL
    j0, j1 = ix * SUBPIXEL, (ix + 1) * SUBPIXEL

    def suma(arr):
        return arr[i1, j1] - arr[i0, j1] - arr[i1, j0] + arr[i0, j0]

    n = suma(m)
    with np.errstate(invalid="ignore", divide="ignore"):
        cx = np.where(n > 0, suma(sx) / np.maximum(n, 1), info["xs"][ix])
        cy = np.where(n > 0, suma(sy) / np.maximum(n, 1), info["ys"][iy])
    return cx, cy, iy, ix


def generar_puntos(mascara, info) -> gpd.GeoDataFrame:
    """Un punto por celda superviviente; columnas en 6372 y 4326."""
    cx, cy, iy, ix = _centroides_celdas(info["mask_sub"], mascara, info)
    pts = gpd.GeoDataFrame(
        {"ix": ix, "iy": iy, "x_6372": cx, "y_6372": cy},
        geometry=gpd.points_from_xy(cx, cy), crs=CRS_TRABAJO,
    )
    pts["id_punto"] = [f"P{i:06d}" for i in range(len(pts))]
    wgs = pts.to_crs(CRS_SALIDA)
    pts["lon"] = wgs.geometry.x.to_numpy()
    pts["lat"] = wgs.geometry.y.to_numpy()
    return pts


# ---------------------------------------------------------------------------
# Contexto territorial y clase por serie
# ---------------------------------------------------------------------------

def asignar_contexto(pts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Entidad y municipio del Marco Geoestadístico 2025."""
    mun = gpd.read_file(MARCO / "00mun.shp").to_crs(CRS_TRABAJO)
    ren = {c.upper(): c for c in mun.columns}
    cols = [ren[k] for k in ("CVEGEO", "CVE_ENT", "NOM_ENT", "NOM_MUN")
            if k in ren]
    j = gpd.sjoin(pts[["id_punto", "geometry"]],
                  mun[cols + ["geometry"]], how="left",
                  predicate="within")
    primero = j.dropna(subset=["CVEGEO"]).drop_duplicates("id_punto")
    pts = pts.merge(primero[["id_punto"] + cols], on="id_punto", how="left")
    return pts.rename(columns={c: c.upper() for c in cols})


def asignar_clases(pts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Clase armonizada de cada serie en la ubicación del punto."""
    base = pts[["id_punto", "geometry"]].copy()
    for serie in SERIES:
        agri = cargar_agricola(serie)
        j = gpd.sjoin(base, agri[["clase", "geometry"]], how="left",
                      predicate="within")
        clase_map = (j.dropna(subset=["clase"])
                     .drop_duplicates("id_punto")
                     .set_index("id_punto")["clase"])
        pts[f"clase_{serie}"] = pts["id_punto"].map(clase_map)
    cols_clase = [f"clase_{s}" for s in SERIES]
    pts["clase_estable"] = pts[cols_clase].nunique(axis=1).eq(1)
    return pts


# ---------------------------------------------------------------------------
# NASA POWER: features climáticas
# ---------------------------------------------------------------------------

def features_celdas() -> pd.DataFrame:
    """
        Agregación anual por celda y serie de cada parámetro POWER.

        return: DataFrame largo con columnas serie, lat, lon, param, store,
        valor (suma anual o media diaria según PARAM_SUM/PARAM_MEDIA).
    """
    cache = NASA_DIR / "features_celdas.parquet"
    if cache.exists():
        return pd.read_parquet(cache)

    frames = []
    for serie in SERIES:
        for parquet in sorted((NASA_DIR / f"serie_{serie}").glob("*.parquet")):
            param = parquet.stem
            df = pd.read_parquet(parquet, columns=["lat", "lon", "value"])
            g = df.groupby(["lat", "lon"])["value"]
            agg = g.sum() if param in PARAM_SUM else g.mean()
            out = agg.rename("valor").reset_index()
            out["serie"] = serie
            out["param"] = param
            out["store"] = STORE_POR_PARAM.get(param, "merra2")
            frames.append(out)
    largo = pd.concat(frames, ignore_index=True)
    largo.to_parquet(cache, index=False)
    return largo


def firma_climatica() -> dict[str, pd.DataFrame]:
    """
        Firma climática por celda: media entre las 7 series de cada
        agregado anual, por store, más derivados en la firma merra2.

        return: {"merra2": df, "syn1deg": df} indexados por (lat, lon).
    """
    cache = NASA_DIR / "firma_climatica.parquet"
    largo = features_celdas()
    if cache.exists():
        z = pd.read_parquet(cache)
        return {s: z[z.store == s].set_index(["lat", "lon"])
                for s in ("merra2", "syn1deg")}

    firmas = {}
    for store in ("merra2", "syn1deg"):
        sub = largo[largo.store == store]
        piv = sub.pivot_table(index=["lat", "lon"], columns="param",
                              values="valor", aggfunc="mean")
        piv.columns = [f"clim_{c}" for c in piv.columns]
        piv.index.names = ["lat", "lon"]
        firmas[store] = piv

    # Derivados sobre merra2: PET anual (mm) y aridez P/PET
    m = firmas["merra2"]
    col_evt = "clim_" + "EVPTRNS"
    col_ppt = "clim_" + "PRECTOTCORR"
    pet = (m[col_evt] * LE_A_MM_DIA * 365 if col_evt in m.columns
           else pd.Series(np.nan, index=m.index))
    m["pet_mm_anual"] = pet
    if col_ppt in m.columns:
        m["aridez"] = m[col_ppt] / pet.replace(0, np.nan)
    if "clim_CDD0" in m.columns and "clim_HDD0" in m.columns:
        m["gdd_anual"] = m["clim_CDD0"] + m["clim_HDD0"]

    out = pd.concat(
        [df.reset_index().assign(store=s) for s, df in firmas.items()],
        ignore_index=True)
    out.to_parquet(cache, index=False)
    return firmas


def asignar_celdas_power(lon, lat):
    """Celda merra2 (0.5x0.625) y syn1deg (1x1) más cercana a cada punto."""
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    m_lat = -90 + np.round((lat + 90) / 0.5) * 0.5
    m_lon = -180 + np.round((lon + 180) / 0.625) * 0.625
    s_lat = -89.5 + np.round(lat + 89.5)
    s_lon = -179.5 + np.round(lon + 179.5)
    return m_lat, m_lon, s_lat, s_lon


def join_clima(pts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Anexa a cada punto las features de su celda merra2 y syn1deg."""
    firmas = firma_climatica()
    m_lat, m_lon, s_lat, s_lon = asignar_celdas_power(pts["lon"], pts["lat"])
    pts["cell_merra2"] = list(zip(m_lat.round(3), m_lon.round(3)))
    pts["cell_syn1deg"] = list(zip(s_lat.round(1), s_lon.round(1)))

    for store, (clat, clon), pref in (
            ("merra2", (m_lat, m_lon), "m_"),
            ("syn1deg", (s_lat, s_lon), "s_")):
        f = firmas[store].reset_index().rename(
            columns={"lat": "clat", "lon": "clon"})
        feat = [c for c in f.columns if c not in ("clat", "clon")]
        f = f.rename(columns={c: pref + c for c in feat})
        tmp = pd.DataFrame({"id_punto": pts["id_punto"],
                            "clat": clat, "clon": clon})
        pts = pts.merge(tmp.merge(f, on=["clat", "clon"], how="left"),
                        on="id_punto", how="left")
    return pts


def caracterizar_clima(pts: gpd.GeoDataFrame,
                       k: int = K_ZONAS) -> gpd.GeoDataFrame:
    """
        KMeans sobre features climáticas estandarizadas -> zona_clima;
        flags de deciles extremos.
    """
    features = [c for c in CLIM_FEATURES if c in pts.columns]
    X = pts[features].apply(pd.to_numeric, errors="coerce")
    X = X.fillna(X.median(numeric_only=True))
    Z = StandardScaler().fit_transform(X)
    pts["zona_clima"] = KMeans(n_clusters=k, random_state=SEMILLA,
                               n_init=10).fit_predict(Z)
    pts["zona_clima"] = "Z" + pts["zona_clima"].astype(str).str.zfill(2)

    for var in CLIM_EXTREMOS:
        if var not in pts.columns:
            continue
        q_lo, q_hi = pts[var].quantile([Q_EXTREMO, 1 - Q_EXTREMO])
        pts[f"extremo_{var}"] = ((pts[var] <= q_lo)
                                 | (pts[var] >= q_hi))
    n_cell = pts.groupby("cell_merra2")["id_punto"].transform("size")
    pts["n_puntos_en_celda_merra2"] = n_cell
    pts["clima_redundante"] = n_cell > 1
    return pts


# ---------------------------------------------------------------------------
# Flujo completo
# ---------------------------------------------------------------------------

def construir_malla(grid_m: int = GRID_M,
                    caracterizar: bool = True) -> gpd.GeoDataFrame:
    """Ejecuta todo el flujo y devuelve el GeoDataFrame de puntos."""
    NASA_DIR.mkdir(parents=True, exist_ok=True)
    extraer_zips()
    mascara, embudo, info_vii = filtro_iterativo(grid_m)
    print(embudo.to_string(index=False))
    pts = generar_puntos(mascara, info_vii)
    print(f"Puntos generados: {len(pts):,}")
    pts = asignar_contexto(pts)
    pts = asignar_clases(pts)
    pts = join_clima(pts)
    if caracterizar:
        pts = caracterizar_clima(pts)
    return pts, embudo


def exportar(pts: gpd.GeoDataFrame, embudo: pd.DataFrame) -> dict[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rutas = {}
    geo = pts.set_geometry("geometry").to_crs(CRS_SALIDA)
    geo.to_file(OUT_DIR / "puntos_malla_clima.gpkg", layer="puntos_malla_clima")
    rutas["gpkg"] = OUT_DIR / "puntos_malla_clima.gpkg"
    csv = pts.drop(columns=["geometry"]).copy()
    csv.to_csv(OUT_DIR / "puntos_malla_clima.csv", index=False)
    rutas["csv"] = OUT_DIR / "puntos_malla_clima.csv"
    embudo.to_csv(OUT_DIR / "embudo_persistencia.csv", index=False)
    rutas["embudo"] = OUT_DIR / "embudo_persistencia.csv"
    return rutas


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fracciones":
        for s in SERIES:
            frac, _ = fraccion_agricola(s)
            print(s, "celdas>=0.5:", int((frac >= 0.5).sum()))
    else:
        pts, embudo = construir_malla()
        rutas = exportar(pts, embudo)
        for k, v in rutas.items():
            print(k, "->", v)
