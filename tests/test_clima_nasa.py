import pandas as pd

from proyecto_agronomia.datasets import clima_nasa


def _respuesta_diaria(inicio: str, fin: str) -> dict:
    fechas = pd.date_range(inicio, fin, freq="D")
    claves = [fecha.strftime("%Y%m%d") for fecha in fechas]
    return {
        "properties": {
            "parameter": {
                "T2M": dict.fromkeys(claves, 20.0),
                "PRECTOTCORR": dict.fromkeys(claves, 1.0),
            }
        }
    }


def test_resumir_nasa_power_considera_anio_bisiesto():
    resultado = clima_nasa.resumir_nasa_power(
        _respuesta_diaria("2023-01-01", "2024-12-31"),
        cvegeo="1001",
        inicio=2023,
        fin=2024,
    )

    assert resultado["cvegeo"].tolist() == ["01001", "01001"]
    assert resultado["dias_temperatura"].tolist() == [365, 366]
    assert resultado["precipitacion_anual_mm"].tolist() == [365.0, 366.0]
    assert resultado["temperatura_media_c"].tolist() == [20.0, 20.0]


def test_descarga_por_celdas_consulta_una_vez_y_asigna_municipios(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    processed = tmp_path / "processed"
    monkeypatch.setattr(clima_nasa, "NASA_POWER_RAW_DIR", raw)
    monkeypatch.setattr(clima_nasa, "NASA_POWER_PROCESSED_DIR", processed)
    consultas = []

    def consulta_simulada(latitud, longitud, inicio, fin, sesion):
        consultas.append((latitud, longitud, inicio, fin))
        return _respuesta_diaria("2023-01-01", "2023-12-31")

    monkeypatch.setattr(clima_nasa, "consultar_nasa_power", consulta_simulada)
    municipios = pd.DataFrame(
        {
            "cvegeo": ["01001", "01002"],
            "Latitud": [21.88, 21.91],
            "Longitud": [-102.29, -102.31],
        }
    )

    resultado = clima_nasa.descargar_clima_nasa_por_celdas(
        municipios, inicio=2023, fin=2023, pausa=0
    )

    assert len(consultas) == 1
    assert len(resultado) == 2
    assert set(resultado["cvegeo"]) == {"01001", "01002"}
    assert resultado["precipitacion_anual_mm"].tolist() == [365.0, 365.0]
    assert (processed / "clima_municipal_2023_2023.csv").exists()
