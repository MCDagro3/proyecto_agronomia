"""Esquemas de pandera para validar la calidad del dataset integrado.

Los esquemas solo verifican; no modifican los datos. Las superficies (Sembrada, Cosechada,
Siniestrada) están en hectáreas según el diccionario DGSIAP
(`references/diccionario_datos_agricultura_dgsiap.xlsx`), por lo que son comparables entre sí.
"""

import re

import numpy as np
import pandas as pd
from pandera.errors import SchemaErrors
import pandera.pandas as pa

from proyecto_agronomia.config import ANIO_FINAL, ANIO_INICIAL, ANIOS, PROCESSED_DATA_DIR

RUTA_DATASET_INTEGRADO = (
    PROCESSED_DATA_DIR / "agricultura_clima_edafologia_historial_2003_2025.csv"
)

# Un municipio puede repartirse entre varios DDR/CADER, por eso forman parte de la llave.
LLAVE_REGISTRO = [
    "Anio",
    "cvegeo",
    "Idddr",
    "Idcader",
    "Idciclo",
    "Idmodalidad",
    "Idcultivo",
    "Idunidadmedida",
]
CICLOS_ANUALES = ["Otoño-Invierno", "Primavera-Verano"]
TOLERANCIA_HA = 0.01
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Reglas cuyo incumplimiento es esperado u orientativo: se reportan como advertencia.
REGLAS_ADVERTENCIA = {
    "perennes_sin_siniestrada",
    "Idestado_un_solo_Nomestado",
    "cvegeo_un_solo_Nommunicipio",
    "Idcultivo_un_solo_Nomcultivo",
    "rendimiento_consistente",
    "suelo_cubre_95pct_municipio",
}

# Columnas donde un faltante es esperado, con la razón.
FALTANTES_ESPERADOS = {
    "Rendimiento": "Nulo cuando Cosechada = 0 (no hay superficie para dividir).",
    "Preciomediorural": "Nulo cuando Volumenproduccion = 0 (no hubo venta).",
    "textura_dominante": "Sin clase textural en la capa INEGI para el municipio 20157.",
    "textura_dominante_pct": "Sin clase textural en la capa INEGI para el municipio 20157.",
    "rendimiento_anio_anterior": "Primer año de la serie o año previo sin cosecha.",
    "rendimiento_hist_media": "Menos de 3 años previos con rendimiento (minimo_periodos=3).",
    "rendimiento_hist_desviacion": "Menos de 3 años previos con rendimiento (minimo_periodos=3).",
    "rendimiento_hist_cv": "Menos de 3 años previos con rendimiento (minimo_periodos=3).",
}


# nombre de regla -> descripción legible; se llena al definir cada check.
DESCRIPCIONES: dict[str, str] = {
    "multiple_fields_uniqueness": "La llave de registro no se repite.",
    "column_in_dataframe": "La columna existe en el dataset.",
}


def _regla(funcion, nombre: str, descripcion: str) -> pa.Check:
    DESCRIPCIONES[nombre] = descripcion
    return pa.Check(funcion, name=nombre)


def _codigo_con_un_nombre(codigo: str, nombre: str) -> pa.Check:
    return _regla(
        lambda df: df.groupby(codigo)[nombre].transform("nunique").le(1),
        f"{codigo}_un_solo_{nombre}",
        f"Cada {codigo} debe tener un único {nombre}.",
    )


def _no_negativo(**kwargs) -> pa.Column:
    return pa.Column(float, pa.Check.ge(0), **kwargs)


# ---------------------------------------------------------------------
# Agrícola
# ---------------------------------------------------------------------

esquema_agricola = pa.DataFrameSchema(
    name="agricola",
    columns={
        "Anio": pa.Column(int, pa.Check.in_range(ANIO_INICIAL, ANIO_FINAL)),
        "Idestado": pa.Column(int, pa.Check.in_range(1, 32)),
        "Nomestado": pa.Column(nullable=False),
        "Idddr": pa.Column(int),
        "Nomddr": pa.Column(nullable=False),
        "Idcader": pa.Column(int),
        "Nomcader": pa.Column(nullable=False),
        "Idmunicipio": pa.Column(int, pa.Check.ge(1)),
        "Nommunicipio": pa.Column(nullable=False),
        "Idciclo": pa.Column(int, pa.Check.isin([1, 2, 3])),
        "Nomcicloproductivo": pa.Column(checks=pa.Check.isin([*CICLOS_ANUALES, "Perennes"])),
        "Idmodalidad": pa.Column(int, pa.Check.isin([1, 2])),
        "Nommodalidad": pa.Column(checks=pa.Check.isin(["Riego", "Temporal"])),
        "Idunidadmedida": pa.Column(int),
        "Nomunidad": pa.Column(
            checks=pa.Check.isin(
                ["Tonelada", "Gruesa", "Planta", "Miles de lts.", "Manojo", "Metro cuadrado"]
            )
        ),
        "Idcultivo": pa.Column(int),
        "Nomcultivo": pa.Column(nullable=False),
        "Sembrada": _no_negativo(),
        "Cosechada": _no_negativo(),
        "Siniestrada": _no_negativo(),
        "Volumenproduccion": _no_negativo(),
        "Rendimiento": _no_negativo(nullable=True),
        "Preciomediorural": _no_negativo(nullable=True),
        "Valorproduccion": _no_negativo(),
        "cvegeo": pa.Column(checks=pa.Check.str_matches(r"^\d{5}$")),
    },
    checks=[
        # Integridad de llaves y catálogos
        _regla(
            lambda df: df["cvegeo"].str[:2].astype(int).eq(df["Idestado"]),
            "cvegeo_prefijo_igual_idestado",
            "Los dos primeros dígitos de cvegeo deben ser Idestado.",
        ),
        _codigo_con_un_nombre("Idestado", "Nomestado"),
        _codigo_con_un_nombre("cvegeo", "Nommunicipio"),
        _codigo_con_un_nombre("Idcultivo", "Nomcultivo"),
        _codigo_con_un_nombre("Idunidadmedida", "Nomunidad"),
        _codigo_con_un_nombre("Idciclo", "Nomcicloproductivo"),
        _codigo_con_un_nombre("Idmodalidad", "Nommodalidad"),
        # Límites de superficie (todas en hectáreas)
        _regla(
            lambda df: df["Cosechada"].le(df["Sembrada"] + TOLERANCIA_HA),
            "cosechada_le_sembrada",
            "Cosechada no puede superar a Sembrada.",
        ),
        _regla(
            lambda df: df["Siniestrada"].le(df["Sembrada"] + TOLERANCIA_HA),
            "siniestrada_le_sembrada",
            "Siniestrada no puede superar a Sembrada.",
        ),
        _regla(
            lambda df: (df["Cosechada"] + df["Siniestrada"]).le(df["Sembrada"] + TOLERANCIA_HA),
            "cosechada_mas_siniestrada_le_sembrada",
            "Cosechada + Siniestrada no puede superar a Sembrada.",
        ),
        _regla(
            lambda df: (
                ~df["Nomcicloproductivo"].isin(CICLOS_ANUALES)
                | (df["Cosechada"] + df["Siniestrada"] - df["Sembrada"]).abs().le(TOLERANCIA_HA)
            ),
            "anuales_cosechada_mas_siniestrada_igual_sembrada",
            "En cultivos anuales, Cosechada + Siniestrada debe ser igual a Sembrada.",
        ),
        _regla(
            lambda df: df["Nomcicloproductivo"].ne("Perennes") | df["Siniestrada"].eq(0),
            "perennes_sin_siniestrada",
            "Según DGSIAP, la superficie siniestrada solo aplica a cultivos anuales.",
        ),
        # Coherencia de producción
        _regla(
            lambda df: df["Cosechada"].gt(0) | df["Volumenproduccion"].eq(0),
            "volumen_cero_si_cosechada_cero",
            "Sin superficie cosechada no puede haber volumen de producción.",
        ),
        _regla(
            lambda df: df["Rendimiento"].notna() | df["Cosechada"].eq(0),
            "rendimiento_nulo_implica_cosechada_cero",
            "Rendimiento solo puede faltar cuando Cosechada = 0.",
        ),
        _regla(
            lambda df: df["Cosechada"].gt(0) | df["Rendimiento"].fillna(0).eq(0),
            "sin_cosecha_rendimiento_nulo_o_cero",
            "Con Cosechada = 0, Rendimiento debe ser nulo o 0.",
        ),
        _regla(
            lambda df: df["Preciomediorural"].notna() | df["Volumenproduccion"].eq(0),
            "precio_nulo_implica_volumen_cero",
            "Preciomediorural solo puede faltar cuando Volumenproduccion = 0.",
        ),
        _regla(
            lambda df: (
                df["Rendimiento"].isna()
                | df["Cosechada"].eq(0)
                | (df["Volumenproduccion"] / df["Cosechada"] - df["Rendimiento"])
                .abs()
                .le((0.01 * df["Rendimiento"]).clip(lower=0.01))
            ),
            "rendimiento_consistente",
            "Rendimiento ≈ Volumen / Cosechada (tolerancia max(0.01, 1 %)).",
        ),
        _regla(
            lambda df: (
                df["Preciomediorural"].isna()
                | df["Valorproduccion"].eq(0)
                | (df["Volumenproduccion"] * df["Preciomediorural"] - df["Valorproduccion"])
                .abs()
                .le(0.01 * df["Valorproduccion"])
            ),
            "valor_consistente",
            "Valorproduccion ≈ Volumen × Precio (tolerancia 1 %).",
        ),
    ],
    unique=LLAVE_REGISTRO,
    report_duplicates="all",
    strict=False,
    coerce=False,
)

# ---------------------------------------------------------------------
# Clima
# ---------------------------------------------------------------------

_temperatura = pa.Check.in_range(-10, 45)
_precip_mensual = pa.Check.in_range(0, 1500)

esquema_clima = pa.DataFrameSchema(
    name="clima",
    columns={
        "temperatura_media_ciclo_c": pa.Column(float, _temperatura),
        "precipitacion_ciclo_mm": pa.Column(float, pa.Check.in_range(0, 6000)),
        "dias_clima_ciclo": pa.Column(int, pa.Check.isin([182, 183, 365, 366])),
        r"temperatura_[a-z]{3}(_anterior)?_c": pa.Column(float, _temperatura, regex=True),
        r"precipitacion_[a-z]{3}(_anterior)?_mm": pa.Column(float, _precip_mensual, regex=True),
    },
    checks=[
        _regla(
            lambda df: (
                df["dias_clima_ciclo"]
                .isin([182, 183])
                .eq(df["Nomcicloproductivo"].isin(CICLOS_ANUALES))
            ),
            "dias_clima_acorde_al_ciclo",
            "Ciclos anuales usan ~6 meses de clima; perennes, un año completo.",
        ),
    ],
)

# ---------------------------------------------------------------------
# Edafología
# ---------------------------------------------------------------------


def _dominante_es_el_maximo(df: pd.DataFrame) -> pd.Series:
    composicion = df.filter(regex=r"^suelo_pct_")
    codigos = composicion.columns.str.removeprefix("suelo_pct_")
    posicion = codigos.get_indexer(df["grupo_suelo_dominante"])
    valores = composicion.to_numpy()
    pct_dominante = np.where(
        posicion >= 0, valores[np.arange(len(df)), posicion.clip(min=0)], np.nan
    )
    return pd.Series(np.abs(pct_dominante - valores.max(axis=1)) <= 0.01, index=df.index)


esquema_edafologia = pa.DataFrameSchema(
    name="edafologia",
    columns={
        r"suelo_pct_[A-Z]{2}": pa.Column(float, pa.Check.in_range(0, 100), regex=True),
        "grupo_suelo_dominante": pa.Column(checks=pa.Check.str_matches(r"^[A-Z]{2}$")),
        "grupo_suelo_dominante_pct": pa.Column(
            float, pa.Check.in_range(0, 100, include_min=False)
        ),
        "nombre_suelo_wrb": pa.Column(nullable=False),
        "grupos_suelo_n": pa.Column(int, pa.Check.ge(1)),
        "textura_dominante": pa.Column(float, pa.Check.isin([1, 2, 3]), nullable=True),
        "textura_dominante_pct": pa.Column(float, pa.Check.in_range(0, 100), nullable=True),
    },
    checks=[
        _regla(
            lambda df: df.filter(regex=r"^suelo_pct_").sum(axis=1).le(100.5),
            "suelo_suma_le_100",
            "La composición de suelo no puede sumar más de 100 %.",
        ),
        _regla(
            lambda df: df.filter(regex=r"^suelo_pct_").sum(axis=1).ge(95),
            "suelo_cubre_95pct_municipio",
            "La capa de suelo cubre al menos 95 % del municipio (falla en costas; esperado).",
        ),
        _regla(
            _dominante_es_el_maximo,
            "dominante_es_el_maximo",
            "grupo_suelo_dominante debe ser el grupo con mayor porcentaje.",
        ),
    ],
)

# ---------------------------------------------------------------------
# Historial de rendimiento
# ---------------------------------------------------------------------

esquema_historial = pa.DataFrameSchema(
    name="historial",
    columns={
        "rendimiento_hist_anios": pa.Column(int, pa.Check.in_range(0, len(ANIOS) - 1)),
        "rendimiento_anio_anterior": _no_negativo(nullable=True),
        "rendimiento_hist_media": _no_negativo(nullable=True),
        "rendimiento_hist_desviacion": _no_negativo(nullable=True),
        "rendimiento_hist_cv": _no_negativo(nullable=True),
    },
    checks=[
        _regla(
            lambda df: (
                df[
                    [
                        "rendimiento_hist_media",
                        "rendimiento_hist_desviacion",
                        "rendimiento_hist_cv",
                    ]
                ]
                .isna()
                .nunique(axis=1)
                .eq(1)
            ),
            "estadisticos_hist_nulos_a_la_vez",
            "media, desviación y CV históricos son nulos o no nulos a la vez.",
        ),
        _regla(
            lambda df: df["rendimiento_hist_anios"].gt(0) | df["rendimiento_anio_anterior"].isna(),
            "sin_anio_anterior_en_primer_anio",
            "Sin años previos no puede haber rendimiento del año anterior.",
        ),
        _regla(
            lambda df: df["rendimiento_hist_anios"].ge(3) | df["rendimiento_hist_media"].isna(),
            "media_hist_requiere_3_anios",
            "La media histórica requiere al menos 3 años previos (sin fuga temporal).",
        ),
    ],
)

ESQUEMAS = {
    "agricola": esquema_agricola,
    "clima": esquema_clima,
    "edafologia": esquema_edafologia,
    "historial": esquema_historial,
}


def unir_esquemas(*esquemas: pa.DataFrameSchema, nombre: str = "integrado"):
    """Combina columnas, checks y unicidad de varios esquemas en uno."""
    columnas, checks, unico = {}, [], None
    for esquema in esquemas:
        columnas.update(esquema.columns)
        checks.extend(esquema.checks)
        unico = unico or esquema.unique
    return pa.DataFrameSchema(
        columnas, checks=checks, unique=unico, report_duplicates="all", name=nombre
    )


esquema_integrado = unir_esquemas(*ESQUEMAS.values())

# ---------------------------------------------------------------------
# Funciones de apoyo
# ---------------------------------------------------------------------


def cargar_dataset_integrado(ruta=RUTA_DATASET_INTEGRADO) -> pd.DataFrame:
    """Lee el CSV integrado conservando cvegeo como texto de 5 dígitos."""
    return pd.read_csv(ruta, dtype={"cvegeo": str}, low_memory=False)


def validar(df: pd.DataFrame, esquema: pa.DataFrameSchema) -> pd.DataFrame:
    """Valida en modo lazy y regresa los casos de falla (vacío si todo pasa)."""
    if not df.index.is_unique:
        raise ValueError("El índice debe ser único para identificar los registros con falla.")
    try:
        esquema.validate(df, lazy=True)
    except SchemaErrors as errores:
        return errores.failure_cases
    return pd.DataFrame(
        columns=["schema_context", "column", "check", "check_number", "failure_case", "index"]
    )


def _reglas_del_esquema(esquema: pa.DataFrameSchema) -> pd.DataFrame:
    """Lista todas las reglas del esquema con el mismo texto que usa pandera en sus fallas."""
    filas = []
    for nombre_col, columna in esquema.columns.items():
        if columna.dtype is not None:
            filas.append((nombre_col, f"dtype('{columna.dtype}')", "Tipo de dato esperado."))
        if not columna.nullable:
            filas.append((nombre_col, "not_nullable", "Sin valores faltantes."))
        for check in columna.checks:
            filas.append((nombre_col, check.error, "Rango o dominio de la columna."))
    for check in esquema.checks:
        filas.append((esquema.name, check.name, DESCRIPCIONES.get(check.name, "")))
    if esquema.unique:
        filas.append(
            (
                esquema.name,
                "multiple_fields_uniqueness",
                DESCRIPCIONES["multiple_fields_uniqueness"],
            )
        )
    return pd.DataFrame(filas, columns=["columna", "regla", "descripcion"])


def _columna_del_esquema(columna: str, esquema: pa.DataFrameSchema) -> str:
    """Traduce una columna real (p. ej. suelo_pct_AC) a su clave regex en el esquema."""
    if columna in esquema.columns:
        return columna
    for clave, definicion in esquema.columns.items():
        if definicion.regex and re.fullmatch(clave, columna):
            return clave
    return columna


def resumen_fallas(
    fallas: pd.DataFrame, esquema: pa.DataFrameSchema, n_registros: int
) -> pd.DataFrame:
    """Tabla con todas las reglas del esquema, su estado y los registros afectados.

    Las reglas a nivel DataFrame aparecen en pandera una vez por columna de cada fila con
    falla; por eso se cuentan índices únicos.
    """
    reglas = _reglas_del_esquema(esquema)
    if fallas.empty:
        conteo = pd.DataFrame(columns=["columna", "regla", "registros"])
    else:
        f = fallas.assign(regla=fallas["check"].astype(str))
        es_tabla = f["schema_context"].eq("DataFrameSchema")
        f["columna"] = np.where(
            es_tabla,
            esquema.name,
            f["column"].astype(str).map(lambda c: _columna_del_esquema(c, esquema)),
        )
        conteo = (
            f.groupby(["columna", "regla"])["index"].nunique().rename("registros").reset_index()
        )
    salida = reglas.merge(conteo, on=["columna", "regla"], how="outer")
    salida["registros"] = salida["registros"].fillna(0).astype(int)
    salida["pct_registros"] = (100 * salida["registros"] / n_registros).round(4)
    falla = salida["registros"].gt(0)
    advertencia = salida["regla"].isin(REGLAS_ADVERTENCIA)
    salida["estado"] = np.select(
        [falla & advertencia, falla], ["Advertencia", "Falla"], default="OK"
    )
    salida.insert(0, "esquema", esquema.name)
    orden = salida["estado"].map({"Falla": 0, "Advertencia": 1, "OK": 2})
    return (
        salida.assign(_orden=orden)
        .sort_values(["_orden", "registros"], ascending=[True, False])
        .drop(columns="_orden")
        .reset_index(drop=True)
    )


def indices_con_falla(fallas: pd.DataFrame, regla: str) -> list:
    """Índices de los registros que violan una regla (nombre del check)."""
    seleccion = fallas.loc[fallas["check"].astype(str).eq(regla), "index"].dropna()
    return sorted(seleccion.unique().tolist())


def reporte_faltantes(df: pd.DataFrame) -> pd.DataFrame:
    """Faltantes por columna, indicando si son esperados y por qué."""
    na = df.isna().sum()
    reporte = pd.DataFrame(
        {"faltantes": na, "pct_faltantes": (100 * na / len(df)).round(4)}
    ).rename_axis("columna")
    reporte["esperado"] = reporte.index.isin(list(FALTANTES_ESPERADOS))
    reporte["explicacion"] = reporte.index.map(FALTANTES_ESPERADOS).fillna("")
    reporte["estado"] = "OK"
    reporte.loc[reporte["faltantes"].gt(0) & reporte["esperado"], "estado"] = "Esperado"
    reporte.loc[reporte["faltantes"].gt(0) & ~reporte["esperado"], "estado"] = "Inesperado"
    return reporte.sort_values("faltantes", ascending=False)
