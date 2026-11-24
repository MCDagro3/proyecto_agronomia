import numpy as np
import pandas as pd

from processing.preparacion_modelado import preparar_dataset_modelado


def _fila(anio, nombre, cosechada, volumen, **cambios):
    fila = {
        "Anio": anio,
        "cvegeo": "01001",
        "Idestado": 1,
        "Nomestado": "Aguascalientes",
        "Nommunicipio": "Aguascalientes",
        "Idcultivo": 7230000,
        "Nomcultivo": nombre,
        "Idciclo": 1,
        "Idmodalidad": 1,
        "Idunidadmedida": 200201,
        "Sembrada": cosechada,
        "Cosechada": cosechada,
        "Siniestrada": 0.0,
        "Volumenproduccion": volumen,
        "Rendimiento": volumen / cosechada if cosechada else 0.0,
        "Preciomediorural": 10.0 if volumen else 0.0,
        "Valorproduccion": volumen * 10.0,
    }
    fila.update(cambios)
    return fila


def test_preparacion_homologa_ausencias_y_usa_ids_en_historial():
    datos = pd.DataFrame(
        [
            _fila(2003, "Jenjibre", 10.0, 20.0),
            _fila(2004, "Jenjibre", 10.0, 40.0),
            _fila(2006, "Jengibre", 10.0, 60.0),
            _fila(2007, "Jengibre", 0.0, 0.0),
        ]
    )

    resultado = preparar_dataset_modelado(datos, minimo_periodos=2).set_index("Anio")

    assert resultado["Nomcultivo_canonico"].eq("Jengibre").all()
    assert resultado.loc[2003, "rendimiento_hist_anios"] == 0
    assert resultado.loc[2004, "rendimiento_hist_anios"] == 1
    assert resultado.loc[2004, "rendimiento_anio_anterior"] == 2.0
    assert resultado.loc[2006, "rendimiento_hist_anios"] == 2
    assert np.isnan(resultado.loc[2006, "rendimiento_anio_anterior"])
    assert resultado.loc[2006, "rendimiento_hist_media"] == 3.0
    assert resultado.loc[2007, "sin_cosecha"]
    assert np.isnan(resultado.loc[2007, "Rendimiento"])
    assert np.isnan(resultado.loc[2007, "Preciomediorural"])
    assert not resultado.loc[2007, "registro_apto_modelado"]


def test_preparacion_conserva_falla_de_calidad_pero_la_excluye_del_modelado():
    datos = pd.DataFrame(
        [
            _fila(
                2025,
                "Pastos y praderas",
                100.0,
                1_000.0,
                Sembrada=99.0,
            )
        ]
    )

    resultado = preparar_dataset_modelado(datos)

    assert len(resultado) == 1
    assert not resultado.loc[0, "calidad_superficie"]
    assert not resultado.loc[0, "registro_calidad_valida"]
    assert not resultado.loc[0, "registro_apto_modelado"]
