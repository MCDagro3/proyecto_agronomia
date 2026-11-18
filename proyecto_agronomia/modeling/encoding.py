"""Preparacion nacional y reduccion dimensional para modelos agricolas."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import TruncatedSVD
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from proyecto_agronomia.config import INTERIM_DATA_DIR, PROCESSED_DATA_DIR


RUTA_DATOS_INTEGRADOS = (
    PROCESSED_DATA_DIR / "agricultura_clima_edafologia_2003_2025.csv"
)
MODELING_INTERIM_DIR = INTERIM_DATA_DIR / "modeling" / "nacional"

COLUMNAS_IDENTIFICACION = [
    "cvegeo", "Anio", "Nomestado", "Nommunicipio", "Nomcultivo",
    "Nomcicloproductivo", "Nommodalidad", "Nomunidad",
]
COLUMNAS_OBJETIVO = [
    "Sembrada", "Cosechada", "Siniestrada", "Volumenproduccion",
    "Rendimiento", "Preciomediorural", "Valorproduccion",
]

MESES = (
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
)
VARIABLES_NUMERICAS = [
    "Anio", "precipitacion_ciclo_mm", "dias_clima_ciclo",
    "temperatura_media_ciclo_c",
    *[f"temperatura_{mes}_c" for mes in MESES],
    *[f"precipitacion_{mes}_mm" for mes in MESES],
    "temperatura_oct_anterior_c", "temperatura_nov_anterior_c",
    "temperatura_dic_anterior_c", "precipitacion_oct_anterior_mm",
    "precipitacion_nov_anterior_mm", "precipitacion_dic_anterior_mm",
    "grupo_suelo_dominante_pct", "textura_dominante_pct",
    "grupos_suelo_n",
]

# En INEGI: 1=gruesa, 2=media y 3=fina; aqui si existe orden fisico.
VARIABLES_ORDINALES = ["textura_dominante"]

# Estas son etiquetas, no distancias; por ello se aplica one-hot.
VARIABLES_NOMINALES = [
    "Nomestado", "Nomcultivo", "Nomcicloproductivo", "Nommodalidad",
    "Nomunidad", "grupo_suelo_dominante",
]

COLUMNAS_LECTURA = list(dict.fromkeys(
    COLUMNAS_IDENTIFICACION + COLUMNAS_OBJETIVO + VARIABLES_NUMERICAS
    + VARIABLES_ORDINALES + VARIABLES_NOMINALES
))


def cargar_datos_nacionales(
    ruta: Path = RUTA_DATOS_INTEGRADOS,
) -> pd.DataFrame:
    """Carga solo las columnas necesarias del dataset integrado completo."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el dataset integrado: {ruta}")
    datos = pd.read_csv(
        ruta, usecols=COLUMNAS_LECTURA, dtype={"cvegeo": "string"},
        low_memory=False,
    )
    datos["cvegeo"] = datos["cvegeo"].str.zfill(5)
    for columna in VARIABLES_NUMERICAS + VARIABLES_ORDINALES + COLUMNAS_OBJETIVO:
        datos[columna] = pd.to_numeric(datos[columna], errors="coerce")
    for columna in VARIABLES_NOMINALES:
        datos[columna] = (
            datos[columna].astype("string").fillna("Sin informacion")
        )
    return datos


def crear_preprocesador() -> ColumnTransformer:
    """Estandariza magnitudes y aplica one-hot a etiquetas nominales."""
    return ColumnTransformer(
        [
            (
                "magnitudes",
                Pipeline([
                    ("imputar", SimpleImputer(
                        strategy="median", keep_empty_features=True,
                    )),
                    ("escalar", StandardScaler()),
                ]),
                VARIABLES_NUMERICAS + VARIABLES_ORDINALES,
            ),
            (
                "nominales",
                Pipeline([
                    ("imputar", SimpleImputer(strategy="most_frequent")),
                    ("one_hot", OneHotEncoder(
                        handle_unknown="ignore", sparse_output=True,
                        dtype=np.float32,
                    )),
                ]),
                VARIABLES_NOMINALES,
            ),
        ],
        sparse_threshold=1.0,
        verbose_feature_names_out=False,
    )


def ajustar_reduccion(
    datos: pd.DataFrame,
    anio_ajuste_final: int = 2021,
    n_componentes: int = 64,
    semilla: int = 42,
) -> tuple[ColumnTransformer, TruncatedSVD]:
    """Ajusta one-hot y SVD solo con el periodo destinado a entrenamiento."""
    mascara = datos["Anio"].le(anio_ajuste_final)
    if not mascara.any():
        raise ValueError("No hay registros en el periodo de ajuste.")
    preprocesador = crear_preprocesador()
    matriz_ajuste = preprocesador.fit_transform(datos.loc[mascara])
    maximo = min(matriz_ajuste.shape) - 1
    if not 1 <= n_componentes <= maximo:
        raise ValueError(
            f"n_componentes debe estar entre 1 y {maximo}; recibido {n_componentes}."
        )
    reductor = TruncatedSVD(
        n_components=n_componentes, algorithm="randomized", n_iter=7,
        random_state=semilla,
    )
    reductor.fit(matriz_ajuste)
    return preprocesador, reductor


def transformar_dataset(
    datos: pd.DataFrame,
    preprocesador: ColumnTransformer,
    reductor: TruncatedSVD,
) -> pd.DataFrame:
    """Transforma todo el periodo y conserva contexto y posibles objetivos."""
    matriz = preprocesador.transform(datos)
    componentes = reductor.transform(matriz).astype("float32")
    nombres = [
        f"componente_{numero:03d}"
        for numero in range(1, componentes.shape[1] + 1)
    ]
    reducidas = pd.DataFrame(componentes, columns=nombres, index=datos.index)
    contexto = [
        columna for columna in COLUMNAS_IDENTIFICACION + COLUMNAS_OBJETIVO
        if columna in datos.columns
    ]
    return pd.concat(
        [datos[contexto].reset_index(drop=True), reducidas.reset_index(drop=True)],
        axis=1,
    )


def guardar_reduccion(
    datos_reducidos: pd.DataFrame,
    preprocesador: ColumnTransformer,
    reductor: TruncatedSVD,
    anio_ajuste_final: int,
    directorio: Path = MODELING_INTERIM_DIR,
) -> dict[str, Path]:
    """Guarda dataset, transformadores y diccionario de trazabilidad."""
    destino = Path(directorio)
    destino.mkdir(parents=True, exist_ok=True)
    rutas = {
        "dataset": destino / "agricultura_modelado_pca_2003_2025.csv",
        "preprocesador": destino / "preprocesador_one_hot.joblib",
        "reductor": destino / "reductor_svd.joblib",
        "diccionario": destino / "diccionario_reduccion.json",
    }
    datos_reducidos.to_csv(rutas["dataset"], index=False)
    joblib.dump(preprocesador, rutas["preprocesador"])
    joblib.dump(reductor, rutas["reductor"])
    componentes = [c for c in datos_reducidos if c.startswith("componente_")]
    contenido = {
        "metodo": "TruncatedSVD sobre variables estandarizadas y one-hot",
        "justificacion": (
            "Equivalente escalable de PCA para una matriz one-hot dispersa; "
            "evita densificar los 825 mil registros."
        ),
        "anio_ajuste_final": anio_ajuste_final,
        "registros": len(datos_reducidos),
        "n_componentes": len(componentes),
        "varianza_explicada_acumulada": float(
            reductor.explained_variance_ratio_.sum()
        ),
        "variables_numericas_estandarizadas": VARIABLES_NUMERICAS,
        "variables_ordinales": {
            "textura_dominante": "1=gruesa, 2=media, 3=fina"
        },
        "variables_one_hot": VARIABLES_NOMINALES,
        "identificadores_no_predictivos": COLUMNAS_IDENTIFICACION,
        "posibles_objetivos_no_predictivos": COLUMNAS_OBJETIVO,
        "columnas_predictoras": componentes,
    }
    rutas["diccionario"].write_text(
        json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return rutas
