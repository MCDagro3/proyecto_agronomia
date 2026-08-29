"""
EDA inicial de producción agrícola 2025 - DGSIAP.

Este script asume que el CSV tiene columnas como:
Anio, Idestado, Nomestado, Idddr, Nomddr, Idcader, Nomcader,
Idmunicipio, Nommunicipio, Idciclo, Nomcicloproductivo,
Idmodalidad, Nommodalidad, Idunidadmedida, Nomunidad,
Idcultivo, Nomcultivo, Sembrada, Cosechada, Siniestrada,
Volumenproduccion, Rendimiento, Preciomediorural, Valorproduccion

Objetivos:
- Revisar estructura y calidad de datos.
- Medir cobertura geográfica y agrícola.
- Analizar producción, valor económico y superficie.
- Calcular tasa de siniestro.
- Generar visualizaciones iniciales.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


# ---------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------

DATA_PATH = Path("data/agricola_2025.csv")
FIG_DIR = Path("figuras")
OUTPUT_DIR = Path("data/processed")

TOP_N = 15


# ---------------------------------------------------------
# CARGA DE DATOS
# ---------------------------------------------------------

def cargar_datos(ruta: Path) -> pd.DataFrame:
    """Carga el CSV agrícola."""
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo: {ruta}\n"
            "Coloca el CSV en data/raw/agricola_2025.csv"
        )

    df = pd.read_csv(ruta, low_memory=False)

    print(f"Archivo cargado correctamente: {ruta}")
    print(f"Filas: {df.shape[0]:,}")
    print(f"Columnas: {df.shape[1]}")

    return df


# ---------------------------------------------------------
# LIMPIEZA Y VALIDACIÓN
# ---------------------------------------------------------

def limpiar_datos(df: pd.DataFrame) -> pd.DataFrame:
    """Realiza limpieza mínima y crea variables derivadas."""
    df = df.copy()

    # Quitar espacios accidentales en nombres de columnas
    df.columns = df.columns.str.strip()

    columnas_numericas = [
        "Sembrada",
        "Cosechada",
        "Siniestrada",
        "Volumenproduccion",
        "Rendimiento",
        "Preciomediorural",
        "Valorproduccion",
    ]

    for col in columnas_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Tasa de superficie siniestrada (%)
    if {"Siniestrada", "Sembrada"}.issubset(df.columns):
        df["Tasa_siniestro"] = (
            df["Siniestrada"]
            .div(df["Sembrada"].where(df["Sembrada"] > 0))
            .mul(100)
        )

    return df


def reporte_calidad(df: pd.DataFrame) -> None:
    """Imprime información general sobre calidad de datos."""
    print("\n" + "=" * 70)
    print("ESTRUCTURA DEL DATASET")
    print("=" * 70)

    print(df.dtypes.to_string())

    print("\n" + "=" * 70)
    print("VALORES NULOS")
    print("=" * 70)

    nulos = df.isna().sum()
    porcentaje = (nulos / len(df) * 100).round(2)

    resumen_nulos = pd.DataFrame(
        {
            "nulos": nulos,
            "porcentaje": porcentaje,
        }
    )

    resumen_nulos = resumen_nulos[resumen_nulos["nulos"] > 0]

    if resumen_nulos.empty:
        print("No se encontraron valores nulos.")
    else:
        print(resumen_nulos.sort_values("nulos", ascending=False).to_string())

    print("\nDuplicados exactos:", df.duplicated().sum())


# ---------------------------------------------------------
# COBERTURA
# ---------------------------------------------------------

def reporte_cobertura(df: pd.DataFrame) -> None:
    """Resume la cobertura geográfica y productiva."""
    print("\n" + "=" * 70)
    print("COBERTURA")
    print("=" * 70)

    campos = {
        "Estados": "Nomestado",
        "DDR": "Nomddr",
        "CADER": "Nomcader",
        "Municipios": "Nommunicipio",
        "Cultivos": "Nomcultivo",
        "Ciclos productivos": "Nomcicloproductivo",
        "Modalidades": "Nommodalidad",
    }

    for nombre, columna in campos.items():
        if columna in df.columns:
            print(f"{nombre}: {df[columna].nunique():,}")


# ---------------------------------------------------------
# TABLAS RESUMEN
# ---------------------------------------------------------

def crear_resumenes(df: pd.DataFrame) -> None:
    """Crea y guarda tablas agregadas útiles."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Cultivos
    cultivos = (
        df.groupby("Nomcultivo", as_index=False)
        .agg(
            Superficie_sembrada=("Sembrada", "sum"),
            Superficie_cosechada=("Cosechada", "sum"),
            Superficie_siniestrada=("Siniestrada", "sum"),
            Volumen_produccion=("Volumenproduccion", "sum"),
            Valor_produccion=("Valorproduccion", "sum"),
        )
    )

    cultivos["Rendimiento_global"] = (
        cultivos["Volumen_produccion"]
        .div(cultivos["Superficie_cosechada"].where(
            cultivos["Superficie_cosechada"] > 0
        ))
    )

    cultivos["Tasa_siniestro"] = (
        cultivos["Superficie_siniestrada"]
        .div(cultivos["Superficie_sembrada"].where(
            cultivos["Superficie_sembrada"] > 0
        ))
        .mul(100)
    )

    cultivos.to_csv(
        OUTPUT_DIR / "resumen_cultivos_2025.csv",
        index=False,
        encoding="utf-8-sig"
    )

    # Estados
    estados = (
        df.groupby("Nomestado", as_index=False)
        .agg(
            Superficie_sembrada=("Sembrada", "sum"),
            Superficie_cosechada=("Cosechada", "sum"),
            Superficie_siniestrada=("Siniestrada", "sum"),
            Volumen_produccion=("Volumenproduccion", "sum"),
            Valor_produccion=("Valorproduccion", "sum"),
        )
    )

    estados["Tasa_siniestro"] = (
        estados["Superficie_siniestrada"]
        .div(estados["Superficie_sembrada"].where(
            estados["Superficie_sembrada"] > 0
        ))
        .mul(100)
    )

    estados.to_csv(
        OUTPUT_DIR / "resumen_estados_2025.csv",
        index=False,
        encoding="utf-8-sig"
    )


# ---------------------------------------------------------
# VISUALIZACIONES
# ---------------------------------------------------------

def guardar_barh(
    datos: pd.DataFrame,
    categoria: str,
    valor: str,
    titulo: str,
    xlabel: str,
    nombre_archivo: str,
) -> None:
    """Guarda una gráfica horizontal."""
    datos = datos.sort_values(valor, ascending=True)

    plt.figure(figsize=(10, 7))
    plt.barh(datos[categoria], datos[valor])
    plt.title(titulo)
    plt.xlabel(xlabel)
    plt.ylabel("")
    plt.tight_layout()
    plt.savefig(FIG_DIR / nombre_archivo, dpi=160)
    plt.close()


def graficar_top_cultivos(df: pd.DataFrame) -> None:
    """Top cultivos por volumen y valor de producción."""
    por_cultivo = (
        df.groupby("Nomcultivo", as_index=False)
        .agg(
            Volumenproduccion=("Volumenproduccion", "sum"),
            Valorproduccion=("Valorproduccion", "sum"),
        )
    )

    top_volumen = por_cultivo.nlargest(TOP_N, "Volumenproduccion")

    guardar_barh(
        top_volumen,
        "Nomcultivo",
        "Volumenproduccion",
        f"Top {TOP_N} cultivos por volumen de producción - 2025",
        "Volumen de producción",
        "01_top_cultivos_volumen.png",
    )

    top_valor = por_cultivo.nlargest(TOP_N, "Valorproduccion")

    guardar_barh(
        top_valor,
        "Nomcultivo",
        "Valorproduccion",
        f"Top {TOP_N} cultivos por valor de producción - 2025",
        "Valor de producción",
        "02_top_cultivos_valor.png",
    )


def graficar_estados(df: pd.DataFrame) -> None:
    """Top estados por valor de producción agrícola."""
    por_estado = (
        df.groupby("Nomestado", as_index=False)
        .agg(Valorproduccion=("Valorproduccion", "sum"))
    )

    top = por_estado.nlargest(TOP_N, "Valorproduccion")

    guardar_barh(
        top,
        "Nomestado",
        "Valorproduccion",
        f"Top {TOP_N} estados por valor de producción - 2025",
        "Valor de producción",
        "03_top_estados_valor.png",
    )


def graficar_siniestro(df: pd.DataFrame) -> None:
    """Estados con mayor tasa agregada de superficie siniestrada."""
    por_estado = (
        df.groupby("Nomestado", as_index=False)
        .agg(
            Sembrada=("Sembrada", "sum"),
            Siniestrada=("Siniestrada", "sum"),
        )
    )

    por_estado["Tasa_siniestro"] = (
        por_estado["Siniestrada"]
        .div(por_estado["Sembrada"].where(por_estado["Sembrada"] > 0))
        .mul(100)
    )

    top = por_estado.nlargest(TOP_N, "Tasa_siniestro")

    guardar_barh(
        top,
        "Nomestado",
        "Tasa_siniestro",
        f"Top {TOP_N} estados por tasa de superficie siniestrada - 2025",
        "Superficie siniestrada (%)",
        "04_estados_tasa_siniestro.png",
    )


def graficar_relacion_superficie_produccion(df: pd.DataFrame) -> None:
    """Relación entre superficie cosechada y volumen producido."""
    datos = df[
        ["Cosechada", "Volumenproduccion"]
    ].dropna()

    datos = datos[
        (datos["Cosechada"] > 0)
        & (datos["Volumenproduccion"] > 0)
    ]

    if datos.empty:
        return

    plt.figure(figsize=(9, 6))
    plt.scatter(
        datos["Cosechada"],
        datos["Volumenproduccion"],
        alpha=0.35,
        s=15,
    )
    plt.xscale("log")
    plt.yscale("log")
    plt.title("Superficie cosechada vs volumen de producción - 2025")
    plt.xlabel("Superficie cosechada (escala log)")
    plt.ylabel("Volumen de producción (escala log)")
    plt.tight_layout()
    plt.savefig(
        FIG_DIR / "05_cosechada_vs_produccion.png",
        dpi=160
    )
    plt.close()


def generar_graficas(df: pd.DataFrame) -> None:
    """Genera todas las gráficas del EDA."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    graficar_top_cultivos(df)
    graficar_estados(df)
    graficar_siniestro(df)
    graficar_relacion_superficie_produccion(df)

    print(f"\nGráficas guardadas en: {FIG_DIR}")


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main() -> None:
    df = cargar_datos(DATA_PATH)
    df = limpiar_datos(df)

    reporte_calidad(df)
    reporte_cobertura(df)

    crear_resumenes(df)
    generar_graficas(df)

    print("\n" + "=" * 70)
    print("EDA 2025 COMPLETADO")
    print("=" * 70)

    print("\nArchivos generados:")
    print("  data/processed/resumen_cultivos_2025.csv")
    print("  data/processed/resumen_estados_2025.csv")
    print("  figuras/01_top_cultivos_volumen.png")
    print("  figuras/02_top_cultivos_valor.png")
    print("  figuras/03_top_estados_valor.png")
    print("  figuras/04_estados_tasa_siniestro.png")
    print("  figuras/05_cosechada_vs_produccion.png")


if __name__ == "__main__":
    main()
