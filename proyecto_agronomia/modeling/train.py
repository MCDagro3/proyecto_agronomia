"""Entrenamiento y evaluacion con los componentes del dataset nacional."""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
import typer

from proyecto_agronomia.modeling.data import preparar_datos_cultivo, separar_xy
from proyecto_agronomia.modeling.registry import guardar_modelo


def _modelo_con_log(modelo) -> TransformedTargetRegressor:
    pipeline = Pipeline([
        ("imputar", SimpleImputer(strategy="median")),
        ("modelo", modelo),
    ])
    return TransformedTargetRegressor(
        regressor=pipeline,
        func=np.log1p,
        inverse_func=np.expm1,
        check_inverse=True,
    )


def crear_candidatos(semilla: int = 42) -> dict[str, TransformedTargetRegressor]:
    """Crea una referencia y dos alternativas no lineales."""
    return {
        "mediana": _modelo_con_log(DummyRegressor(strategy="median")),
        "hist_gradient_boosting": _modelo_con_log(
            HistGradientBoostingRegressor(
                learning_rate=0.06,
                max_iter=300,
                max_leaf_nodes=31,
                min_samples_leaf=20,
                l2_regularization=1.0,
                random_state=semilla,
            )
        ),
        "random_forest": _modelo_con_log(
            RandomForestRegressor(
                n_estimators=250,
                min_samples_leaf=5,
                max_features=0.7,
                n_jobs=-1,
                random_state=semilla,
            )
        ),
    }


def crear_particiones(
    datos: pd.DataFrame,
    anio_prueba: int = 2022,
    proporcion_municipios: float = 0.20,
    semilla: int = 42,
) -> dict[str, pd.Index]:
    """Crea entrenamiento, prueba temporal y prueba espacio-temporal."""
    if not 0 < proporcion_municipios < 1:
        raise ValueError("proporcion_municipios debe estar entre 0 y 1.")
    municipios = np.array(sorted(datos["cvegeo"].dropna().unique()))
    if len(municipios) < 5:
        raise ValueError("No hay suficientes municipios para validacion espacial.")
    generador = np.random.default_rng(semilla)
    cantidad = max(1, round(len(municipios) * proporcion_municipios))
    reservados = set(generador.choice(municipios, size=cantidad, replace=False))
    es_reservado = datos["cvegeo"].isin(reservados)
    es_futuro = datos["Anio"].ge(anio_prueba)
    particiones = {
        "entrenamiento": datos.index[~es_futuro & ~es_reservado],
        "prueba_temporal": datos.index[es_futuro & ~es_reservado],
        "prueba_espaciotemporal": datos.index[es_futuro & es_reservado],
    }
    if any(len(indices) == 0 for indices in particiones.values()):
        raise ValueError("Alguna particion quedo vacia; ajusta los parametros.")
    return particiones


def calcular_metricas(y_real, y_predicho) -> dict[str, float]:
    """Calcula metricas en la escala original del rendimiento."""
    return {
        "mae": float(mean_absolute_error(y_real, y_predicho)),
        "rmse": float(np.sqrt(mean_squared_error(y_real, y_predicho))),
        "r2": float(r2_score(y_real, y_predicho)),
        "sesgo": float(np.mean(np.asarray(y_predicho) - np.asarray(y_real))),
    }


def comparar_modelos(
    datos: pd.DataFrame,
    particiones: dict[str, pd.Index],
    semilla: int = 42,
) -> tuple[dict[str, object], pd.DataFrame]:
    """Entrena candidatos y evalua temporal y espacio-temporalmente."""
    modelos = crear_candidatos(semilla)
    X, y = separar_xy(datos)
    resultados = []
    entrenados: dict[str, object] = {}
    indice_entrenamiento = particiones["entrenamiento"]
    for nombre, modelo in modelos.items():
        modelo.fit(X.loc[indice_entrenamiento], y.loc[indice_entrenamiento])
        entrenados[nombre] = modelo
        for particion in ["prueba_temporal", "prueba_espaciotemporal"]:
            indices = particiones[particion]
            prediccion = modelo.predict(X.loc[indices])
            resultados.append({
                "modelo": nombre,
                "particion": particion,
                "registros": len(indices),
                **calcular_metricas(y.loc[indices], prediccion),
            })
    return entrenados, pd.DataFrame(resultados)


def seleccionar_modelo(metricas: pd.DataFrame) -> str:
    """Elige por RMSE espacio-temporal y usa RMSE temporal como desempate."""
    tabla = metricas.pivot(index="modelo", columns="particion", values="rmse")
    return str(tabla.sort_values(
        ["prueba_espaciotemporal", "prueba_temporal"]
    ).index[0])


def entrenar_modelo_final(modelo_entrenado, datos: pd.DataFrame):
    """Clona la configuracion ganadora y la ajusta con todos los datos."""
    X, y = separar_xy(datos)
    modelo_final = clone(modelo_entrenado)
    modelo_final.fit(X, y)
    return modelo_final


app = typer.Typer()


@app.command()
def main(
    cultivo: str = typer.Option("Maíz grano"),
    version: str = typer.Option("v2_pca"),
    unidad: str | None = typer.Option(None),
    anio_prueba: int = typer.Option(2022),
    semilla: int = typer.Option(42),
    ruta_datos: Path | None = typer.Option(None),
):
    """Entrena, selecciona y registra un modelo con componentes PCA/SVD."""
    parametros = {"cultivo": cultivo, "unidad": unidad}
    if ruta_datos is not None:
        parametros["ruta"] = ruta_datos
    datos, unidad_usada = preparar_datos_cultivo(**parametros)
    particiones = crear_particiones(datos, anio_prueba=anio_prueba, semilla=semilla)
    entrenados, metricas = comparar_modelos(datos, particiones, semilla=semilla)
    ganador = seleccionar_modelo(metricas)
    modelo_final = entrenar_modelo_final(entrenados[ganador], datos)
    variables = list(separar_xy(datos)[0].columns)
    destino = guardar_modelo(
        modelo=modelo_final,
        cultivo=cultivo,
        version=version,
        metadata={
            "algoritmo": ganador,
            "unidad": unidad_usada,
            "anio_prueba": anio_prueba,
            "semilla": semilla,
            "registros": len(datos),
            "municipios": datos["cvegeo"].nunique(),
            "representacion": "one-hot + TruncatedSVD",
        },
        metricas={"comparacion": metricas.to_dict(orient="records")},
        variables=variables,
    )
    typer.echo(metricas.to_string(index=False))
    typer.echo(f"Modelo seleccionado: {ganador}")
    typer.echo(f"Guardado en: {destino}")


if __name__ == "__main__":
    app()
