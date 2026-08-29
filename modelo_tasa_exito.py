"""Entrena y utiliza un modelo de tasa de éxito por estado y cultivo.

La tasa de éxito se define como Cosechada / Sembrada * 100. El entrenamiento
agrega primero las filas de cada combinación estado-cultivo para no dar más
peso accidentalmente a combinaciones divididas en muchos municipios o ciclos.
"""

from __future__ import annotations

import argparse
from difflib import get_close_matches
from pathlib import Path
import unicodedata

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "agricola_2025.csv"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
DATOS_MODELO_PATH = PROCESSED_DIR / "datos_modelo_tasa_exito.csv"
MODELO_PATH = PROCESSED_DIR / "modelo_tasa_exito.joblib"
SEMILLA = 42


def preparar_datos(ruta: Path) -> pd.DataFrame:
    """Limpia y agrega los datos necesarios para el modelo."""
    columnas = ["Nomestado", "Nomcultivo", "Sembrada", "Cosechada"]
    df = pd.read_csv(ruta, usecols=columnas, encoding="utf-8-sig")
    df["Sembrada"] = pd.to_numeric(df["Sembrada"], errors="coerce")
    df["Cosechada"] = pd.to_numeric(df["Cosechada"], errors="coerce")
    df["Nomestado"] = df["Nomestado"].astype("string").str.strip()
    df["Nomcultivo"] = df["Nomcultivo"].astype("string").str.strip()

    validos = df[
        df["Nomestado"].notna()
        & df["Nomcultivo"].notna()
        & df["Sembrada"].gt(0)
        & df["Cosechada"].ge(0)
    ].copy()
    descartados = len(df) - len(validos)

    datos = (
        validos.groupby(["Nomestado", "Nomcultivo"], as_index=False)
        .agg(Sembrada=("Sembrada", "sum"), Cosechada=("Cosechada", "sum"))
    )
    datos["Tasa_exito"] = 100 * datos["Cosechada"] / datos["Sembrada"]

    # Una tasa física fuera de [0, 100] indica una inconsistencia del registro.
    anomalos = ~datos["Tasa_exito"].between(0, 100)
    print(f"Filas originales: {len(df):,}")
    print(f"Filas descartadas por datos inválidos: {descartados:,}")
    print(f"Combinaciones estado-cultivo anómalas descartadas: {anomalos.sum():,}")
    datos = datos.loc[~anomalos].reset_index(drop=True)

    if len(datos) < 20:
        raise ValueError("No hay suficientes combinaciones válidas para entrenar.")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    datos.to_csv(DATOS_MODELO_PATH, index=False, encoding="utf-8-sig")
    return datos


def crear_modelo() -> Pipeline:
    """Crea el preprocesamiento categórico y el regresor."""
    try:
        codificador = OneHotEncoder(handle_unknown="ignore", sparse_output=True)
    except TypeError:  # scikit-learn < 1.2
        codificador = OneHotEncoder(handle_unknown="ignore", sparse=True)
    preprocesador = ColumnTransformer(
        [("categorias", codificador, ["Nomestado", "Nomcultivo"])],
        remainder="drop",
    )
    regresor = RandomForestRegressor(
        n_estimators=300,
        min_samples_leaf=2,
        max_features=0.8,
        random_state=SEMILLA,
        n_jobs=-1,
    )
    return Pipeline([("preprocesador", preprocesador), ("modelo", regresor)])


def entrenar(ruta_csv: Path, ruta_modelo: Path) -> None:
    """Entrena, evalúa y guarda el modelo junto con su catálogo."""
    datos = preparar_datos(ruta_csv)
    x = datos[["Nomestado", "Nomcultivo"]]
    y = datos["Tasa_exito"]
    pesos = datos["Sembrada"]
    x_train, x_test, y_train, y_test, w_train, _ = train_test_split(
        x, y, pesos, test_size=0.20, random_state=SEMILLA
    )

    modelo = crear_modelo()
    modelo.fit(x_train, y_train, modelo__sample_weight=w_train)
    prediccion = modelo.predict(x_test).clip(0, 100)
    mae = mean_absolute_error(y_test, prediccion)
    rmse = mean_squared_error(y_test, prediccion) ** 0.5
    r2 = r2_score(y_test, prediccion)
    referencia = mean_absolute_error(y_test, [y_train.mean()] * len(y_test))

    # Se reentrena con todos los registros después de medir el desempeño.
    modelo.fit(x, y, modelo__sample_weight=pesos)
    artefacto = {
        "modelo": modelo,
        "estados": sorted(datos["Nomestado"].unique().tolist()),
        "cultivos": sorted(datos["Nomcultivo"].unique().tolist()),
        "definicion": "100 * superficie cosechada / superficie sembrada",
        "metricas_prueba": {"mae": mae, "rmse": rmse, "r2": r2},
    }
    ruta_modelo.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artefacto, ruta_modelo)

    print(f"Combinaciones usadas: {len(datos):,}")
    print(f"MAE de prueba: {mae:.2f} puntos porcentuales")
    print(f"RMSE de prueba: {rmse:.2f} puntos porcentuales")
    print(f"R² de prueba: {r2:.3f}")
    print(f"MAE de referencia (predecir la media): {referencia:.2f}")
    print(f"Datos preparados: {DATOS_MODELO_PATH}")
    print(f"Modelo guardado: {ruta_modelo}")


def texto_normalizado(texto: str) -> str:
    """Normaliza mayúsculas y acentos para aceptar entradas cómodas."""
    texto = unicodedata.normalize("NFKD", texto.strip().casefold())
    return "".join(c for c in texto if not unicodedata.combining(c))


def resolver_categoria(valor: str, catalogo: list[str], nombre: str) -> str:
    """Devuelve la escritura canónica de una categoría o un error útil."""
    indice = {texto_normalizado(item): item for item in catalogo}
    clave = texto_normalizado(valor)
    if clave in indice:
        return indice[clave]
    cercanas = get_close_matches(clave, indice.keys(), n=3, cutoff=0.5)
    sugerencias = ", ".join(indice[c] for c in cercanas)
    detalle = f" ¿Quisiste decir: {sugerencias}?" if sugerencias else ""
    raise ValueError(f"{nombre} no reconocido: {valor!r}.{detalle}")


def predecir(ruta_modelo: Path, estado: str, cultivo: str) -> None:
    """Carga el modelo y predice la tasa para una combinación."""
    if not ruta_modelo.exists():
        raise FileNotFoundError("Primero entrena el modelo con el comando 'entrenar'.")
    artefacto = joblib.load(ruta_modelo)
    estado = resolver_categoria(estado, artefacto["estados"], "Estado")
    cultivo = resolver_categoria(cultivo, artefacto["cultivos"], "Cultivo")
    entrada = pd.DataFrame({"Nomestado": [estado], "Nomcultivo": [cultivo]})
    tasa = float(artefacto["modelo"].predict(entrada)[0])
    tasa = min(100.0, max(0.0, tasa))
    print(f"Estado: {estado}")
    print(f"Cultivo: {cultivo}")
    print(f"Tasa de éxito estimada: {tasa:.2f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subcomandos = parser.add_subparsers(dest="comando", required=True)
    p_entrenar = subcomandos.add_parser("entrenar", help="Procesa y entrena.")
    p_entrenar.add_argument("--csv", type=Path, default=CSV_PATH)
    p_entrenar.add_argument("--modelo", type=Path, default=MODELO_PATH)
    p_predecir = subcomandos.add_parser("predecir", help="Realiza una predicción.")
    p_predecir.add_argument("--estado", required=True)
    p_predecir.add_argument("--cultivo", required=True)
    p_predecir.add_argument("--modelo", type=Path, default=MODELO_PATH)
    args = parser.parse_args()

    if args.comando == "entrenar":
        entrenar(args.csv.resolve(), args.modelo.resolve())
    else:
        predecir(args.modelo.resolve(), args.estado, args.cultivo)


if __name__ == "__main__":
    main()
