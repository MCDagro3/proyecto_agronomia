"""
Exploración inicial de datos agrícolas DGSIAP - Cierre 2025.

Fuente:
https://nube.agricultura.gob.mx/index.php?view=10AE434F-A2158368-A120BC5A-EDF4AFAA&ANIO=2025

El script:
1. Descarga el archivo 2025 desde DGSIAP.
2. Detecta encoding y separador de forma tolerante.
3. Muestra estructura, tipos, nulos y estadísticas.
4. Guarda una copia CSV local.
5. Genera gráficas básicas para las columnas numéricas.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import csv

import matplotlib.pyplot as plt
import pandas as pd
import requests


URL = (
    "https://nube.agricultura.gob.mx/index.php"
    "?view=10AE434F-A2158368-A120BC5A-EDF4AFAA&ANIO=2025"
)

DATA_DIR = Path("data")
FIG_DIR = Path("figuras")
CSV_SALIDA = DATA_DIR / "agricola_2025.csv"


def descargar_archivo(url: str) -> bytes:
    """Descarga el archivo desde DGSIAP y devuelve sus bytes."""
    print("Descargando datos de DGSIAP...")
    response = requests.get(url, timeout=120)
    response.raise_for_status()

    print(f"Descarga completada: {len(response.content) / (1024**2):.2f} MB")
    print(f"Content-Type: {response.headers.get('Content-Type', 'desconocido')}")
    return response.content


def detectar_encoding(contenido: bytes) -> str:
    """Prueba encodings comunes en archivos CSV del gobierno."""
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            contenido[:100_000].decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "latin-1"


def detectar_separador(texto: str) -> str:
    """Detecta entre coma, punto y coma, tabulador o pipe."""
    muestra = texto[:20_000]

    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t|")
        return dialecto.delimiter
    except csv.Error:
        return ","


def cargar_dataframe(contenido: bytes) -> pd.DataFrame:
    """Carga el archivo descargado en un DataFrame."""
    encoding = detectar_encoding(contenido)
    texto_muestra = contenido[:100_000].decode(encoding, errors="replace")
    separador = detectar_separador(texto_muestra)

    print(f"Encoding detectado: {encoding}")
    print(f"Separador detectado: {repr(separador)}")

    df = pd.read_csv(
        BytesIO(contenido),
        sep=separador,
        encoding=encoding,
        low_memory=False,
    )

    # Normalizamos encabezados para facilitar análisis posteriores.
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace(r"\s+", "_", regex=True)
    )

    return df


def resumen_dataframe(df: pd.DataFrame) -> None:
    """Imprime información útil para la exploración inicial."""
    print("\n" + "=" * 70)
    print("DIMENSIONES")
    print("=" * 70)
    print(f"Filas:    {df.shape[0]:,}")
    print(f"Columnas: {df.shape[1]:,}")

    print("\n" + "=" * 70)
    print("COLUMNAS")
    print("=" * 70)
    for i, columna in enumerate(df.columns, start=1):
        print(f"{i:02d}. {columna} ({df[columna].dtype})")

    print("\n" + "=" * 70)
    print("PRIMERAS 5 FILAS")
    print("=" * 70)
    print(df.head().to_string())

    print("\n" + "=" * 70)
    print("VALORES NULOS")
    print("=" * 70)
    nulos = df.isna().sum().sort_values(ascending=False)
    nulos = nulos[nulos > 0]

    if nulos.empty:
        print("No se detectaron valores nulos.")
    else:
        print(nulos.to_string())

    print("\n" + "=" * 70)
    print("ESTADÍSTICAS NUMÉRICAS")
    print("=" * 70)
    numericas = df.select_dtypes(include="number")

    if numericas.empty:
        print("No se detectaron columnas numéricas.")
    else:
        print(numericas.describe().T.to_string())


def graficar_numericas(df: pd.DataFrame, max_columnas: int = 6) -> None:
    """
    Genera histogramas de hasta `max_columnas` variables numéricas.
    Cada gráfica se guarda como PNG individual.
    """
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    numericas = df.select_dtypes(include="number").columns.tolist()

    if not numericas:
        print("\nNo hay columnas numéricas para graficar.")
        return

    print("\nGenerando histogramas...")

    for columna in numericas[:max_columnas]:
        serie = df[columna].dropna()

        if serie.empty:
            continue

        plt.figure(figsize=(9, 5))
        plt.hist(serie, bins=30)
        plt.title(f"Distribución de {columna}")
        plt.xlabel(columna)
        plt.ylabel("Frecuencia")
        plt.tight_layout()

        ruta = FIG_DIR / f"hist_{columna}.png"
        plt.savefig(ruta, dpi=150)
        plt.close()

        print(f"  Guardada: {ruta}")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    contenido = descargar_archivo(URL)
    df = cargar_dataframe(contenido)

    df.to_csv(CSV_SALIDA, index=False, encoding="utf-8-sig")
    print(f"\nCSV normalizado guardado en: {CSV_SALIDA}")

    resumen_dataframe(df)
    graficar_numericas(df)

    print("\nExploración inicial terminada.")


if __name__ == "__main__":
    main()
