"""Pruebas del cruce MapBiomas × municipios × suelos con un raster sintético."""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from proyecto_agronomia.processing.integracion_edafologica import (
    resumir_edafologia_municipal,
    resumir_edafologia_por_mascara,
)
from proyecto_agronomia.processing.integracion_mapbiomas import (
    area_pixeles_por_fila,
    asignar_mascara_mapbiomas,
    contar_suelo_por_mascara_estado,
)

PASO = 0.01  # grados
N = 100  # píxeles por lado: la malla cubre lon -100..-99, lat 20..21
TRANSFORM = from_origin(-100.0, 21.0, PASO, PASO)


def _escribir(ruta, datos):
    with rasterio.open(
        ruta,
        "w",
        driver="GTiff",
        width=N,
        height=N,
        count=1,
        dtype="uint8",
        crs="EPSG:4326",
        transform=TRANSFORM,
        nodata=0,
    ) as destino:
        destino.write(datos, 1)


@pytest.fixture
def escenario(tmp_path):
    # Municipio A: mitad oeste; municipio B: mitad este.
    municipios = gpd.GeoDataFrame(
        {"cvegeo": ["01001", "01002"]},
        geometry=[box(-100, 20, -99.5, 21), box(-99.5, 20, -99, 21)],
        crs="EPSG:4326",
    )
    # Suelo VR (textura 3) en la mitad norte y LP (textura 1) en la sur.
    suelos = gpd.GeoDataFrame(
        {"Grupo1": ["VR", "LP"], "Clase_tex": [3, 1]},
        geometry=[box(-100, 20.5, -99, 21), box(-100, 20, -99, 20.5)],
        crs="EPSG:4326",
    )
    vacio = np.full((N, N), 66, dtype="uint8")  # matorral
    anio_2002 = vacio.copy()
    anio_2002[:50, :50] = 19  # cultivo anual: A, norte
    anio_2002[:50, 50:] = 19  # anual en B, norte: se traslapa con el perenne de 2003
    anio_2003 = vacio.copy()
    anio_2003[:50, 50:] = 36  # cultivo perenne: B, norte
    anio_2003[50:, :50] = 21  # mosaico de usos: excluido de toda máscara
    anio_2004 = vacio.copy()
    anio_2004[50:, 50:] = 15  # pastizal: B, sur
    rutas = {}
    for anio, datos in [(2002, anio_2002), (2003, anio_2003), (2004, anio_2004)]:
        rutas[anio] = tmp_path / f"{anio}.tif"
        _escribir(rutas[anio], datos)
    return rutas, municipios, suelos


def _area_cuadrante(fila_ini):
    return area_pixeles_por_fila(TRANSFORM, N)[fila_ini : fila_ini + 50].sum() * 50


def test_area_pixel_ecuador():
    # Un píxel de 0.01° en el ecuador mide ~1113 m de lado.
    area = area_pixeles_por_fila(from_origin(0, 0.005, PASO, PASO), 1)[0]
    assert area == pytest.approx(1111.95**2, rel=1e-3)


def test_ventana_movil_y_mascaras(escenario):
    rutas, municipios, suelos = escenario
    tabla = contar_suelo_por_mascara_estado(
        rutas, municipios, suelos, anios=[2003, 2004], tamanio_bloque=32
    )
    tabla = tabla.set_index(["Anio", "mascara", "cvegeo", "Grupo1"])["area_m2"]

    norte, sur = _area_cuadrante(0), _area_cuadrante(50)
    # 2003 usa 2002-2004: ve el anual de 2002, el perenne de 2003 y el
    # pastizal de 2004.
    assert tabla[(2003, "anual", "01001", "VR")] == pytest.approx(norte)
    assert tabla[(2003, "anual", "01002", "VR")] == pytest.approx(norte)
    assert tabla[(2003, "perenne", "01002", "VR")] == pytest.approx(norte)
    assert tabla[(2003, "pastizal", "01002", "LP")] == pytest.approx(sur)
    # La máscara agrícola es la unión 19+36: en B norte hubo 19 y 36 dentro
    # de la ventana y el área no se duplica.
    assert tabla[(2003, "agricola", "01001", "VR")] == pytest.approx(norte)
    assert tabla[(2003, "agricola", "01002", "VR")] == pytest.approx(norte)
    # 2004 usa 2003-2004 (no hay 2005): ya no hay anual; perenne y pastizal sí.
    assert (2004, "anual") not in tabla.droplevel([2, 3]).index
    assert tabla[(2004, "perenne", "01002", "VR")] == pytest.approx(norte)
    assert tabla[(2004, "pastizal", "01002", "LP")] == pytest.approx(sur)
    assert tabla[(2004, "agricola", "01002", "VR")] == pytest.approx(norte)
    # El mosaico (21) no entra en ninguna máscara y nada sale de su municipio.
    assert len(tabla) == 9  # 2003: 6 filas; 2004: 3
    assert "01001" not in tabla.xs("LP", level="Grupo1").index.get_level_values("cvegeo")


def test_falta_anio_de_ventana(escenario):
    rutas, municipios, suelos = escenario
    del rutas[2002]
    with pytest.raises(FileNotFoundError):
        contar_suelo_por_mascara_estado(rutas, municipios, suelos, anios=[2003])


def test_asignar_mascara():
    cultivos = pd.Series(
        [
            "Maíz grano",
            "Pastos y praderas",
            "Alfalfa verde",
            "Avena forrajera en verde",
            "Pasto tapete",
            "Aguacate",
        ]
    )
    ciclos = pd.Series(
        [
            "Primavera-Verano",
            "Primavera-Verano",
            "Perennes",
            "Otoño-Invierno",
            "Perennes",
            "Perennes",
        ]
    )
    assert asignar_mascara_mapbiomas(cultivos, ciclos).tolist() == [
        "anual",
        "pastizal",
        "perenne",
        "anual",
        "pastizal",
        "perenne",
    ]


def test_asignar_mascara_ciclo_desconocido():
    with pytest.raises(ValueError):
        asignar_mascara_mapbiomas(pd.Series(["Maíz grano"]), pd.Series(["Invierno"]))


def test_resumen_por_mascara_con_respaldo(escenario):
    rutas, municipios, suelos = escenario
    conteos = contar_suelo_por_mascara_estado(
        rutas, municipios, suelos, anios=[2003], tamanio_bloque=32
    )
    municipal = resumir_edafologia_municipal(
        municipios.to_crs("EPSG:6372"), suelos.to_crs("EPSG:6372")
    )
    llaves = pd.DataFrame(
        {
            "cvegeo": ["01001", "01002", "01002", "01001"],
            "Anio": [2003, 2003, 2003, 2003],
            "mascara": ["anual", "perenne", "pastizal", "pastizal"],
        }
    )
    resumen = resumir_edafologia_por_mascara(conteos, municipal, llaves).set_index(
        ["cvegeo", "mascara"]
    )
    assert len(resumen) == 4
    # Con máscara: 100 % del suelo de su cuadrante.
    assert resumen.loc[("01001", "anual"), "suelo_fuente"] == "mascara"
    assert resumen.loc[("01001", "anual"), "suelo_pct_VR"] == pytest.approx(100)
    assert resumen.loc[("01002", "pastizal"), "grupo_suelo_dominante"] == "LP"
    # 01001 no tiene pastizal: respaldo municipal (mitad VR, mitad LP).
    respaldo = resumen.loc[("01001", "pastizal")]
    assert respaldo["suelo_fuente"] == "municipal"
    assert respaldo["area_mascara_ha"] == 0
    assert respaldo["suelo_pct_VR"] == pytest.approx(50, abs=1)


def test_respaldo_perenne_en_mascara_agricola(escenario):
    rutas, municipios, suelos = escenario
    conteos = contar_suelo_por_mascara_estado(
        rutas, municipios, suelos, anios=[2003, 2004], tamanio_bloque=32
    )
    municipal = resumir_edafologia_municipal(
        municipios.to_crs("EPSG:6372"), suelos.to_crs("EPSG:6372")
    )
    llaves = pd.DataFrame(
        {
            "cvegeo": ["01001", "01002", "01001"],
            "Anio": [2003, 2003, 2004],
            "mascara": ["perenne", "perenne", "perenne"],
        }
    )
    resumen = resumir_edafologia_por_mascara(conteos, municipal, llaves).set_index(
        ["cvegeo", "Anio"]
    )
    # 01001 no tiene clase 36 en 2003, pero sí 19: usa la tierra agrícola.
    fila = resumen.loc[("01001", 2003)]
    assert fila["suelo_fuente"] == "agricola"
    assert fila["area_mascara_ha"] == 0
    assert fila["suelo_pct_VR"] == pytest.approx(100)
    # 01002 tiene su propia máscara perenne.
    assert resumen.loc[("01002", 2003), "suelo_fuente"] == "mascara"
    # 01001 en 2004 (ventana 2003-2004) no tiene ni 19 ni 36: municipio completo.
    fila = resumen.loc[("01001", 2004)]
    assert fila["suelo_fuente"] == "municipal"
    assert fila["suelo_pct_VR"] == pytest.approx(50, abs=1)
