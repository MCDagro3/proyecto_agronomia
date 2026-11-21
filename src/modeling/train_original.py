"""Modelos equivalentes a v1 para entrenamiento de varios cultivos."""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

from modeling.cultivos import (
    VARIABLES_CATEGORICAS,
    VARIABLES_NUMERICAS,
    separar_xy,
)
from modeling.train import calcular_metricas


def crear_preprocesador_original() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("numericas", SimpleImputer(strategy="median"), VARIABLES_NUMERICAS),
            (
                "categoricas",
                Pipeline(
                    [
                        ("imputar", SimpleImputer(strategy="most_frequent")),
                        (
                            "codificar",
                            OrdinalEncoder(
                                handle_unknown="use_encoded_value",
                                unknown_value=-1,
                                encoded_missing_value=-2,
                            ),
                        ),
                    ]
                ),
                VARIABLES_CATEGORICAS,
            ),
        ],
        verbose_feature_names_out=False,
    )


def _con_log(modelo):
    return TransformedTargetRegressor(
        regressor=Pipeline(
            [
                ("preparar", crear_preprocesador_original()),
                ("modelo", modelo),
            ]
        ),
        func=np.log1p,
        inverse_func=np.expm1,
        check_inverse=True,
    )


def crear_candidatos_originales(semilla: int = 42) -> dict[str, object]:
    return {
        "mediana": _con_log(DummyRegressor(strategy="median")),
        "hist_gradient_boosting": _con_log(
            HistGradientBoostingRegressor(
                learning_rate=0.06,
                max_iter=300,
                max_leaf_nodes=31,
                min_samples_leaf=20,
                l2_regularization=1.0,
                random_state=semilla,
            )
        ),
        "random_forest": _con_log(
            RandomForestRegressor(
                n_estimators=250,
                min_samples_leaf=5,
                max_features=0.7,
                n_jobs=-1,
                random_state=semilla,
            )
        ),
    }


def comparar_modelos_originales(datos, particiones, semilla: int = 42):
    X, y = separar_xy(datos)
    entrenados, resultados = {}, []
    for nombre, modelo in crear_candidatos_originales(semilla).items():
        modelo.fit(X.loc[particiones["entrenamiento"]], y.loc[particiones["entrenamiento"]])
        entrenados[nombre] = modelo
        for particion in ("prueba_temporal", "prueba_espaciotemporal"):
            indices = particiones[particion]
            prediccion = modelo.predict(X.loc[indices])
            resultados.append(
                {
                    "modelo": nombre,
                    "particion": particion,
                    "registros": len(indices),
                    **calcular_metricas(y.loc[indices], prediccion),
                }
            )
    return entrenados, pd.DataFrame(resultados)
