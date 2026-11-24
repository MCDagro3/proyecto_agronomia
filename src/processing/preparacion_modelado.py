"""Prepara el dataset integrado para entrenamiento sin alterar la fuente original.

La salida conserva todos los registros, agrega banderas de calidad, homologa la
ausencia estructural de producción y recalcula las características históricas
con identificadores estables y sin fuga temporal.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from proyecto_agronomia.config import ANIO_FINAL, ANIO_INICIAL, PROCESSED_DATA_DIR


RUTA_ENTRADA = (
    PROCESSED_DATA_DIR
    / f"agricultura_clima_edafologia_historial_{ANIO_INICIAL}_{ANIO_FINAL}.csv"
)
RUTA_SALIDA = (
    PROCESSED_DATA_DIR / f"agricultura_modelado_{ANIO_INICIAL}_{ANIO_FINAL}.csv"
)

CLAVES_HISTORIA_MODELO = [
    "cvegeo",
    "Idcultivo",
    "Idciclo",
    "Idmodalidad",
    "Idunidadmedida",
]
COLUMNAS_HISTORICAS = [
    "rendimiento_hist_anios",
    "rendimiento_anio_anterior",
    "rendimiento_hist_media",
    "rendimiento_hist_desviacion",
    "rendimiento_hist_cv",
]
COLUMNAS_REQUERIDAS = {
    *CLAVES_HISTORIA_MODELO,
    "Anio",
    "Idestado",
    "Nomestado",
    "Nommunicipio",
    "Nomcultivo",
    "Sembrada",
    "Cosechada",
    "Siniestrada",
    "Volumenproduccion",
    "Rendimiento",
    "Preciomediorural",
    "Valorproduccion",
}

TOLERANCIA_HA = 0.01
TOLERANCIA_RELATIVA_VALOR = 0.01
MINIMO_PERIODOS_HISTORIA = 3


def _validar_columnas(datos: pd.DataFrame) -> None:
    faltantes = COLUMNAS_REQUERIDAS - set(datos.columns)
    if faltantes:
        raise KeyError(f"Faltan columnas para preparar el modelado: {sorted(faltantes)}")


def _convertir_numericas(datos: pd.DataFrame) -> pd.DataFrame:
    salida = datos.copy()
    columnas = [
        "Anio",
        "Sembrada",
        "Cosechada",
        "Siniestrada",
        "Volumenproduccion",
        "Rendimiento",
        "Preciomediorural",
        "Valorproduccion",
    ]
    salida[columnas] = salida[columnas].apply(pd.to_numeric, errors="coerce")
    salida["cvegeo"] = salida["cvegeo"].astype("string").str.zfill(5)
    return salida


def agregar_nombres_canonicos(datos: pd.DataFrame) -> pd.DataFrame:
    """Agrega nombres vigentes sin reemplazar las etiquetas históricas de la fuente."""
    salida = datos.copy()
    correspondencias = [
        ("Idestado", "Nomestado", "Nomestado_canonico"),
        ("cvegeo", "Nommunicipio", "Nommunicipio_canonico"),
        ("Idcultivo", "Nomcultivo", "Nomcultivo_canonico"),
    ]
    for codigo, nombre, canonico in correspondencias:
        catalogo = (
            salida.loc[salida[[codigo, nombre, "Anio"]].notna().all(axis=1)]
            .sort_values([codigo, "Anio", nombre])
            .drop_duplicates(codigo, keep="last")[[codigo, nombre]]
            .rename(columns={nombre: canonico})
        )
        salida = salida.merge(catalogo, on=codigo, how="left", validate="many_to_one")
    return salida


def agregar_banderas_calidad(datos: pd.DataFrame) -> pd.DataFrame:
    """Marca inconsistencias sin borrar ni corregir silenciosamente la fuente."""
    salida = datos.copy()
    sembrada = salida["Sembrada"]
    cosechada = salida["Cosechada"]
    siniestrada = salida["Siniestrada"]
    volumen = salida["Volumenproduccion"]
    precio = salida["Preciomediorural"]
    valor = salida["Valorproduccion"]

    salida["calidad_superficie"] = (
        cosechada.le(sembrada + TOLERANCIA_HA)
        & siniestrada.le(sembrada + TOLERANCIA_HA)
        & (cosechada + siniestrada).le(sembrada + TOLERANCIA_HA)
    )
    salida["calidad_volumen"] = cosechada.gt(0) | volumen.eq(0)
    diferencia_valor = (volumen * precio - valor).abs()
    salida["calidad_valor"] = (
        precio.isna()
        | valor.eq(0)
        | diferencia_valor.le(TOLERANCIA_RELATIVA_VALOR * valor.abs())
    )

    rendimiento_calculado = (volumen / cosechada).where(cosechada.gt(0))
    tolerancia_rendimiento = (0.01 * salida["Rendimiento"]).clip(lower=0.01)
    salida["calidad_rendimiento_fuente"] = (
        salida["Rendimiento"].isna()
        | cosechada.eq(0)
        | rendimiento_calculado.sub(salida["Rendimiento"]).abs().le(tolerancia_rendimiento)
    )
    salida["registro_calidad_valida"] = salida[
        ["calidad_superficie", "calidad_volumen", "calidad_valor"]
    ].all(axis=1)
    return salida


def normalizar_ausencias_estructurales(datos: pd.DataFrame) -> pd.DataFrame:
    """Representa como nulo lo que no existe porque no hubo cosecha o producción."""
    salida = datos.copy()
    salida["sin_cosecha"] = salida["Cosechada"].le(0)
    salida["sin_produccion"] = salida["Volumenproduccion"].le(0)
    salida.loc[salida["sin_cosecha"], "Rendimiento"] = np.nan
    salida.loc[salida["sin_produccion"], "Preciomediorural"] = np.nan
    salida["Rendimiento_modelado"] = (
        salida["Volumenproduccion"] / salida["Cosechada"]
    ).where(salida["Cosechada"].gt(0))
    salida["Rendimiento_modelado"] = salida["Rendimiento_modelado"].replace(
        [np.inf, -np.inf], np.nan
    )
    salida["registro_apto_modelado"] = (
        salida["registro_calidad_valida"]
        & salida["Cosechada"].gt(0)
        & salida["Volumenproduccion"].gt(0)
        & salida["Rendimiento_modelado"].gt(0)
    )
    return salida


def agregar_historial_modelado(
    datos: pd.DataFrame,
    minimo_periodos: int = MINIMO_PERIODOS_HISTORIA,
) -> pd.DataFrame:
    """Calcula historia previa con IDs estables y únicamente observaciones aptas.

    ``rendimiento_anio_anterior`` exige el año calendario t-1. La media,
    desviación y CV del año t usan exclusivamente años menores que t.
    """
    if minimo_periodos < 2:
        raise ValueError("minimo_periodos debe ser al menos 2.")

    salida = datos.drop(columns=COLUMNAS_HISTORICAS, errors="ignore").copy()
    aptos = salida.loc[salida["registro_apto_modelado"]].copy()
    claves_anuales = [*CLAVES_HISTORIA_MODELO, "Anio"]
    anual = (
        aptos.groupby(claves_anuales, as_index=False, observed=True, dropna=False)
        .agg(
            Cosechada=("Cosechada", "sum"),
            Volumenproduccion=("Volumenproduccion", "sum"),
        )
        .sort_values(claves_anuales)
    )
    anual["rendimiento_anual"] = (
        anual["Volumenproduccion"] / anual["Cosechada"]
    ).where(anual["Cosechada"].gt(0))
    grupos = anual.groupby(CLAVES_HISTORIA_MODELO, observed=True, dropna=False)
    rendimiento_previo = grupos["rendimiento_anual"].shift(1)
    anio_previo = grupos["Anio"].shift(1)

    anual["rendimiento_hist_anios"] = grupos["rendimiento_anual"].transform(
        lambda serie: serie.shift(1).expanding().count()
    ).astype("int64")
    anual["rendimiento_anio_anterior"] = rendimiento_previo.where(
        anual["Anio"].sub(anio_previo).eq(1)
    )
    anual["rendimiento_hist_media"] = grupos["rendimiento_anual"].transform(
        lambda serie: serie.shift(1).expanding(min_periods=minimo_periodos).mean()
    )
    anual["rendimiento_hist_desviacion"] = grupos["rendimiento_anual"].transform(
        lambda serie: serie.shift(1).expanding(min_periods=minimo_periodos).std()
    )
    anual["rendimiento_hist_cv"] = (
        anual["rendimiento_hist_desviacion"] / anual["rendimiento_hist_media"]
    ).replace([np.inf, -np.inf], np.nan)

    historia = anual[[*claves_anuales, *COLUMNAS_HISTORICAS]]
    resultado = salida.merge(historia, on=claves_anuales, how="left", validate="many_to_one")
    if len(resultado) != len(datos):
        raise AssertionError("El historial para modelado alteró el número de registros.")
    return resultado


def preparar_dataset_modelado(
    datos: pd.DataFrame,
    minimo_periodos: int = MINIMO_PERIODOS_HISTORIA,
) -> pd.DataFrame:
    """Ejecuta toda la preparación y devuelve un nuevo DataFrame."""
    _validar_columnas(datos)
    n_original = len(datos)
    salida = _convertir_numericas(datos)
    salida = agregar_nombres_canonicos(salida)
    salida = agregar_banderas_calidad(salida)
    salida = normalizar_ausencias_estructurales(salida)
    salida = agregar_historial_modelado(salida, minimo_periodos=minimo_periodos)

    if len(salida) != n_original:
        raise AssertionError("La preparación alteró el número de registros.")
    if not salida["cvegeo"].str.fullmatch(r"\d{5}").all():
        raise AssertionError("Se encontraron claves cvegeo inválidas.")
    return salida


def generar_dataset_modelado(
    ruta_entrada: Path = RUTA_ENTRADA,
    ruta_salida: Path = RUTA_SALIDA,
    minimo_periodos: int = MINIMO_PERIODOS_HISTORIA,
) -> pd.DataFrame:
    """Carga el integrado, genera el producto de modelado y lo guarda en CSV."""
    ruta_entrada = Path(ruta_entrada)
    ruta_salida = Path(ruta_salida)
    if not ruta_entrada.is_file():
        raise FileNotFoundError(f"No se encontró el dataset integrado: {ruta_entrada}")
    if ruta_entrada.resolve() == ruta_salida.resolve():
        raise ValueError("La salida no puede sobrescribir el dataset integrado.")

    datos = pd.read_csv(ruta_entrada, dtype={"cvegeo": "string"}, low_memory=False)
    resultado = preparar_dataset_modelado(datos, minimo_periodos=minimo_periodos)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    resultado.to_csv(ruta_salida, index=False, encoding="utf-8")

    calidad_invalida = (~resultado["registro_calidad_valida"]).sum()
    aptos = resultado["registro_apto_modelado"].sum()
    print(f"Dataset de entrada: {ruta_entrada}")
    print(f"Dataset de modelado: {ruta_salida}")
    print(f"Registros conservados: {len(resultado):,}")
    print(f"Registros con falla estricta de calidad: {calidad_invalida:,}")
    print(f"Registros aptos para modelado: {aptos:,}")
    return resultado


def _crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=RUTA_ENTRADA)
    parser.add_argument("--salida", type=Path, default=RUTA_SALIDA)
    parser.add_argument("--minimo-periodos", type=int, default=MINIMO_PERIODOS_HISTORIA)
    return parser


def main() -> None:
    argumentos = _crear_parser().parse_args()
    generar_dataset_modelado(
        ruta_entrada=argumentos.entrada,
        ruta_salida=argumentos.salida,
        minimo_periodos=argumentos.minimo_periodos,
    )


if __name__ == "__main__":
    main()
