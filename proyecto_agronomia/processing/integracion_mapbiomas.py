"""Cruce de la máscara agrícola de MapBiomas con municipios y suelos INEGI.

Para cada estado se recorren sus rasters anuales por bloques. En cada píxel
se conoce el municipio, la unidad de suelo (``Grupo1`` + ``Clase_tex``) y la
clase MapBiomas de cada año. Para el año t, un píxel pertenece a la máscara
"anual" (clase 19), "perenne" (36) o "pastizal" (15) si tuvo esa clase en t-1,
t o t+1 (ventana móvil para absorber el ruido interanual de la clasificación y
los barbechos). El resultado es el área (m²) de cada unidad de suelo dentro de
cada máscara, por municipio y año.

Cada registro agrícola SIAP se asigna a una máscara con
:func:`asignar_mascara_mapbiomas`, de modo que su suelo se describe solo con el
área del municipio donde ese año hay su tipo de cobertura.
"""

from collections.abc import Iterable, Mapping
import json
from pathlib import Path

import geopandas as gpd
from loguru import logger
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window, from_bounds
from rasterio.windows import bounds as limites_ventana
from rasterio.windows import transform as transformacion_ventana

from proyecto_agronomia.config import (
    ANIOS,
    MAPBIOMAS_INTERIM_DIR,
    MAPBIOMAS_RAW_DIR,
    MAPBIOMAS_VENTANA_ANIOS,
)
from proyecto_agronomia.datasets.mapbiomas import (
    CLAVE_NACIONAL,
    MASCARAS_MAPBIOMAS,
    listar_rasters_mapbiomas,
)

# Radio de la esfera autálica de WGS84 (misma área total que el elipsoide).
RADIO_AUTALICO_M = 6_371_007.181
TAMANIO_BLOQUE = 2048

# Cultivos SIAP que se representan con la máscara de pastizal (clase 15),
# sin importar su ciclo. Lista explícita: los forrajes anuales (avena, maíz,
# sorgo...) van a "anual" y la alfalfa o el nopal forrajero a "perenne".
CULTIVOS_PASTIZAL = frozenset(
    {
        "Pastos y praderas",
        "Pastos y praderas achicalado",
        "Pastos y praderas seco",
        "Pasto tapete",
        "Semilla de pastos y praderas",
        "Semilla de zacate",
    }
)


# Ciclo productivo SIAP -> máscara (cuando el cultivo no es pasto/zacate).
MASCARA_POR_CICLO = {
    "Primavera-Verano": "anual",
    "Otoño-Invierno": "anual",
    "Perennes": "perenne",
}


def asignar_mascara_mapbiomas(nomcultivo: pd.Series, nomciclo: pd.Series) -> pd.Series:
    """Máscara MapBiomas de cada registro SIAP: ``anual``, ``perenne`` o ``pastizal``.

    Los pastos y zacates (``CULTIVOS_PASTIZAL``) van a ``pastizal`` aunque se
    reporten en un ciclo anual; el resto se asigna por su ciclo productivo.
    """
    nombres = nomcultivo.astype("string").str.strip()
    ciclos = nomciclo.astype("string").str.strip()
    no_contemplados = set(ciclos.dropna()) - set(MASCARA_POR_CICLO)
    if ciclos.isna().any() or no_contemplados:
        raise ValueError(f"Ciclos productivos no contemplados: {sorted(no_contemplados)}")
    mascara = ciclos.map(MASCARA_POR_CICLO).astype("string")
    mascara[nombres.isin(CULTIVOS_PASTIZAL)] = "pastizal"
    return mascara


def area_pixeles_por_fila(transform, alto: int) -> np.ndarray:
    """Área (m²) de un píxel de cada fila en una malla geográfica (grados)."""
    if transform.b != 0 or transform.d != 0:
        raise ValueError("La malla debe estar alineada a los ejes.")
    ancho_rad = np.deg2rad(abs(transform.a))
    filas = np.arange(alto + 1)
    latitudes = np.deg2rad(transform.f + filas * transform.e)
    return RADIO_AUTALICO_M**2 * ancho_rad * np.abs(np.diff(np.sin(latitudes)))


def _unidades_suelo(suelos: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Asigna un id entero (desde 1) a cada combinación Grupo1 + Clase_tex."""
    suelos = suelos[["Grupo1", "Clase_tex", "geometry"]].copy()
    suelos["Grupo1"] = suelos["Grupo1"].astype("string").str.strip()
    suelos["Clase_tex"] = pd.to_numeric(suelos["Clase_tex"], errors="coerce")
    catalogo = (
        suelos[["Grupo1", "Clase_tex"]]
        .drop_duplicates()
        .sort_values(["Grupo1", "Clase_tex"], na_position="last")
        .reset_index(drop=True)
    )
    catalogo["unidad_id"] = np.arange(1, len(catalogo) + 1, dtype="int32")
    suelos = suelos.merge(catalogo, on=["Grupo1", "Clase_tex"], how="left")
    return suelos, catalogo


def _rasterizar(capa: gpd.GeoDataFrame, columna: str, ventana, transform, forma) -> np.ndarray:
    """Rasteriza en la ventana solo los polígonos que la intersectan."""
    indices = capa.sindex.intersection(limites_ventana(ventana, transform))
    if len(indices) == 0:
        return np.zeros(forma, dtype="int32")
    sub = capa.iloc[indices]
    return rasterize(
        zip(sub.geometry, sub[columna]),
        out_shape=forma,
        transform=transformacion_ventana(ventana, transform),
        fill=0,
        dtype="int32",
    )


def contar_suelo_por_mascara_estado(
    rutas_por_anio: Mapping[int, Path],
    municipios: gpd.GeoDataFrame,
    suelos: gpd.GeoDataFrame,
    anios: Iterable[int] = ANIOS,
    mascaras: Mapping[str, frozenset[int]] = MASCARAS_MAPBIOMAS,
    ventana_anios: int = MAPBIOMAS_VENTANA_ANIOS,
    tamanio_bloque: int = TAMANIO_BLOQUE,
) -> pd.DataFrame:
    """Área de cada unidad de suelo dentro de cada máscara, por municipio y año.

    ``municipios`` debe contener solo los municipios del estado del raster.
    Devuelve columnas ``cvegeo, Anio, mascara, Grupo1, Clase_tex, area_m2``.
    Los píxeles sin unidad de suelo (p. ej. lagunas no cubiertas por INEGI)
    se conservan con ``Grupo1`` nulo para que cuenten en el área de la
    máscara.
    """
    anios = sorted(int(anio) for anio in anios)
    anios_raster = sorted(rutas_por_anio)
    # Todo el periodo y su ventana deben existir, salvo años posteriores al
    # último publicado (en 2025 la ventana se trunca a 2024-2025).
    necesarios = {
        a
        for anio in anios
        for a in range(anio - ventana_anios, anio + ventana_anios + 1)
        if a <= max(anios_raster)
    }
    faltantes = sorted(necesarios - set(anios_raster))
    if faltantes:
        raise FileNotFoundError(f"Faltan rasters MapBiomas para {faltantes}.")

    fuentes = {anio: rasterio.open(rutas_por_anio[anio]) for anio in anios_raster}
    try:
        referencia = fuentes[anios_raster[0]]
        for anio, fuente in fuentes.items():
            if fuente.shape != referencia.shape or fuente.transform != referencia.transform:
                raise ValueError(f"El raster de {anio} no coincide con la malla de referencia.")
        crs = referencia.crs
        transform = referencia.transform
        alto, ancho = referencia.shape
        area_fila = area_pixeles_por_fila(transform, alto)

        municipios = municipios[["cvegeo", "geometry"]].to_crs(crs).reset_index(drop=True)
        municipios["mun_id"] = np.arange(1, len(municipios) + 1, dtype="int32")
        suelos = suelos.to_crs(crs)
        suelos = suelos.iloc[suelos.sindex.intersection(municipios.total_bounds)]
        suelos, catalogo = _unidades_suelo(suelos)
        n_unidades = len(catalogo) + 1  # 0 = sin unidad de suelo
        n_bins = (len(municipios) + 1) * n_unidades

        acumulado = {
            (anio, mascara): np.zeros(n_bins, dtype="float64")
            for anio in anios
            for mascara in mascaras
        }
        clases = {mascara: np.array(sorted(valores)) for mascara, valores in mascaras.items()}
        posicion = {anio: i for i, anio in enumerate(anios_raster)}

        # Solo se recorre la caja de los municipios recibidos; así un raster
        # nacional se procesa estado por estado sin leerlo completo.
        caja = from_bounds(*municipios.total_bounds, transform=transform)
        fila_ini = max(0, int(np.floor(caja.row_off)))
        col_ini = max(0, int(np.floor(caja.col_off)))
        fila_fin = min(alto, int(np.ceil(caja.row_off + caja.height)))
        col_fin = min(ancho, int(np.ceil(caja.col_off + caja.width)))
        for fila in range(fila_ini, fila_fin, tamanio_bloque):
            for columna in range(col_ini, col_fin, tamanio_bloque):
                ventana = Window(
                    columna,
                    fila,
                    min(tamanio_bloque, col_fin - columna),
                    min(tamanio_bloque, fila_fin - fila),
                )
                forma = (int(ventana.height), int(ventana.width))
                mun = _rasterizar(municipios, "mun_id", ventana, transform, forma)
                if not mun.any():
                    continue
                suelo = _rasterizar(suelos, "unidad_id", ventana, transform, forma)
                pesos = np.broadcast_to(area_fila[fila : fila + forma[0], None], forma)
                llave = mun.astype("int64") * n_unidades + suelo
                pila = np.stack([fuentes[anio].read(1, window=ventana) for anio in anios_raster])
                for mascara, valores in clases.items():
                    en_mascara = np.isin(pila, valores)
                    for anio in anios:
                        i = posicion[anio]
                        desde = max(0, i - ventana_anios)
                        hasta = min(len(anios_raster), i + ventana_anios + 1)
                        seleccion = en_mascara[desde:hasta].any(axis=0) & (mun > 0)
                        if seleccion.any():
                            acumulado[(anio, mascara)] += np.bincount(
                                llave[seleccion],
                                weights=pesos[seleccion],
                                minlength=n_bins,
                            )
    finally:
        for fuente in fuentes.values():
            fuente.close()

    cvegeo_por_id = np.concatenate([[None], municipios["cvegeo"].to_numpy()])
    catalogo_completo = pd.concat(
        [pd.DataFrame({"Grupo1": [pd.NA], "Clase_tex": [np.nan], "unidad_id": [0]}), catalogo],
        ignore_index=True,
    ).set_index("unidad_id")
    tablas = []
    for (anio, mascara), areas in acumulado.items():
        bins = np.flatnonzero(areas)
        if len(bins) == 0:
            continue
        unidad = bins % n_unidades
        tabla = pd.DataFrame(
            {
                "cvegeo": cvegeo_por_id[bins // n_unidades],
                "Anio": anio,
                "mascara": mascara,
                "Grupo1": catalogo_completo.loc[unidad, "Grupo1"].to_numpy(),
                "Clase_tex": catalogo_completo.loc[unidad, "Clase_tex"].to_numpy(),
                "area_m2": areas[bins],
            }
        )
        tablas.append(tabla)
    columnas = ["cvegeo", "Anio", "mascara", "Grupo1", "Clase_tex", "area_m2"]
    if not tablas:
        return pd.DataFrame(columns=columnas)
    resultado = pd.concat(tablas, ignore_index=True)[columnas]
    resultado["cvegeo"] = resultado["cvegeo"].astype("string")
    resultado["Grupo1"] = resultado["Grupo1"].astype("string")
    return resultado


def contar_suelo_por_mascara(
    municipios: gpd.GeoDataFrame,
    suelos: gpd.GeoDataFrame,
    directorio_rasters: Path = MAPBIOMAS_RAW_DIR,
    directorio_cache: Path = MAPBIOMAS_INTERIM_DIR / "suelo_por_mascara",
    anios: Iterable[int] = ANIOS,
    mascaras: Mapping[str, frozenset[int]] = MASCARAS_MAPBIOMAS,
    recalcular: bool = False,
) -> pd.DataFrame:
    """Aplica :func:`contar_suelo_por_mascara_estado` a todos los estados.

    Cada estado se guarda en ``<directorio_cache>/<clave>.parquet``; si ya
    existe se reutiliza, de modo que una corrida interrumpida se reanuda. Si
    la caché se generó con otras máscaras, años o ventana, se borra completa.
    """
    anios = sorted(int(anio) for anio in anios)
    directorio_cache = Path(directorio_cache)
    directorio_cache.mkdir(parents=True, exist_ok=True)
    parametros = {
        "anios": anios,
        "mascaras": {nombre: sorted(clases) for nombre, clases in sorted(mascaras.items())},
        "ventana_anios": MAPBIOMAS_VENTANA_ANIOS,
    }
    ruta_parametros = directorio_cache / "parametros.json"
    vigentes = ruta_parametros.exists() and json.loads(ruta_parametros.read_text()) == parametros
    if not vigentes or recalcular:
        for vieja in directorio_cache.glob("*.parquet"):
            vieja.unlink()
        ruta_parametros.write_text(json.dumps(parametros, indent=2))
    municipios = municipios[["cvegeo", "geometry"]].copy()
    municipios["cvegeo"] = municipios["cvegeo"].astype("string").str.zfill(5)
    rasters = listar_rasters_mapbiomas(directorio_rasters)
    # Se reproyecta una sola vez a la malla de MapBiomas (EPSG:4326).
    with rasterio.open(next(iter(next(iter(rasters.values())).values()))) as fuente:
        crs = fuente.crs
    municipios = municipios.to_crs(crs)
    suelos = suelos[["Grupo1", "Clase_tex", "geometry"]].to_crs(crs)
    claves = sorted(municipios["cvegeo"].str[:2].unique())
    tablas = []
    for clave in claves:
        # Se prefiere el raster nacional; si no existe, el del estado.
        rutas = rasters.get(CLAVE_NACIONAL) or rasters.get(clave)
        if rutas is None:
            raise FileNotFoundError(f"No hay raster MapBiomas nacional ni del estado {clave}.")
        cache = directorio_cache / f"{clave}.parquet"
        if cache.exists():
            tablas.append(pd.read_parquet(cache))
            continue
        municipios_estado = municipios.loc[municipios["cvegeo"].str[:2] == clave]
        logger.info(f"MapBiomas × suelo: estado {clave} ({len(municipios_estado)} municipios).")
        tabla = contar_suelo_por_mascara_estado(
            rutas, municipios_estado, suelos, anios, mascaras=mascaras
        )
        tabla.to_parquet(cache, index=False)
        tablas.append(tabla)
    return pd.concat(tablas, ignore_index=True)
