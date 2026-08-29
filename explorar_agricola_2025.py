"""Exploración y visualización de la producción agrícola de México en 2025."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import pandas as pd
import requests


BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "agricola_2025.csv"
FIG_DIR = BASE_DIR / "figuras"
OUTPUT_DIR = BASE_DIR / "data" / "processed"
URL = ("https://nube.agricultura.gob.mx/index.php"
       "?view=10AE434F-A2158368-A120BC5A-EDF4AFAA&ANIO=2025")
TOP_N = 15
NUMERICAS = ["Anio", "Sembrada", "Cosechada", "Siniestrada",
             "Volumenproduccion", "Rendimiento", "Preciomediorural",
             "Valorproduccion"]
REQUERIDAS = {"Nomestado", "Nomcultivo", "Sembrada", "Cosechada",
              "Siniestrada", "Volumenproduccion", "Valorproduccion"}


def detectar_formato(ruta: Path) -> tuple[str, str]:
    """Detecta encoding y separador del archivo."""
    contenido = ruta.read_bytes()[:100_000]
    encoding = "latin-1"
    for candidato in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            texto = contenido.decode(candidato)
            encoding = candidato
            break
        except UnicodeDecodeError:
            continue
    try:
        separador = csv.Sniffer().sniff(texto, delimiters=",;\t|").delimiter
    except csv.Error:
        separador = ","
    return encoding, separador


def descargar_csv(ruta: Path) -> None:
    """Descarga el CSV únicamente cuando se usa --descargar."""
    print("Descargando datos de DGSIAP...")
    respuesta = requests.get(URL, timeout=120)
    respuesta.raise_for_status()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(respuesta.content)
    print(f"Descarga completada: {len(respuesta.content) / 1024**2:,.2f} MB")


def cargar_datos(ruta: Path) -> pd.DataFrame:
    """Carga, valida y normaliza el CSV agrícola."""
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró {ruta}. Usa --descargar para obtener el archivo."
        )
    encoding, separador = detectar_formato(ruta)
    df = pd.read_csv(ruta, sep=separador, encoding=encoding, low_memory=False)
    df.columns = df.columns.astype(str).str.strip()
    faltantes = sorted(REQUERIDAS - set(df.columns))
    if faltantes:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(faltantes)}")
    for columna in NUMERICAS:
        if columna in df:
            df[columna] = pd.to_numeric(df[columna], errors="coerce")
    df["Tasa_siniestro"] = df["Siniestrada"].div(
        df["Sembrada"].where(df["Sembrada"] > 0)
    ) * 100
    print(f"Archivo: {ruta}")
    print(f"Formato: {encoding}, separador {separador!r}")
    print(f"Dimensiones: {len(df):,} filas × {len(df.columns)} columnas")
    return df


def mostrar_reporte(df: pd.DataFrame) -> None:
    """Imprime calidad, cobertura y estadísticas útiles."""
    print("\n=== CALIDAD DE LOS DATOS ===")
    nulos = df.isna().sum()
    nulos = nulos[nulos > 0].sort_values(ascending=False)
    print("Nulos:\n" + (nulos.to_string() if not nulos.empty else "Ninguno"))
    print(f"Duplicados exactos: {df.duplicated().sum():,}")

    print("\n=== COBERTURA ===")
    campos = {"Estados": "Nomestado", "DDR": "Nomddr", "CADER": "Nomcader",
              "Municipios": "Nommunicipio", "Cultivos": "Nomcultivo",
              "Ciclos": "Nomcicloproductivo", "Modalidades": "Nommodalidad"}
    for etiqueta, columna in campos.items():
        if columna in df:
            print(f"{etiqueta}: {df[columna].nunique(dropna=True):,}")
    disponibles = [c for c in NUMERICAS[1:] if c in df]
    print("\n=== ESTADÍSTICAS NUMÉRICAS ===")
    print(df[disponibles].describe().T.to_string())


def crear_resumenes(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Crea y guarda agregados por cultivo y estado."""
    agregaciones = {
        "Superficie_sembrada": ("Sembrada", "sum"),
        "Superficie_cosechada": ("Cosechada", "sum"),
        "Superficie_siniestrada": ("Siniestrada", "sum"),
        "Volumen_produccion": ("Volumenproduccion", "sum"),
        "Valor_produccion": ("Valorproduccion", "sum"),
    }
    cultivos = df.groupby("Nomcultivo", as_index=False).agg(**agregaciones)
    estados = df.groupby("Nomestado", as_index=False).agg(**agregaciones)
    for resumen in (cultivos, estados):
        resumen["Rendimiento_global"] = resumen["Volumen_produccion"].div(
            resumen["Superficie_cosechada"].where(
                resumen["Superficie_cosechada"] > 0))
        resumen["Tasa_siniestro"] = resumen["Superficie_siniestrada"].div(
            resumen["Superficie_sembrada"].where(
                resumen["Superficie_sembrada"] > 0)) * 100
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cultivos.to_csv(OUTPUT_DIR / "resumen_cultivos_2025.csv", index=False,
                    encoding="utf-8-sig")
    estados.to_csv(OUTPUT_DIR / "resumen_estados_2025.csv", index=False,
                   encoding="utf-8-sig")
    return cultivos, estados


def formato_compacto(valor: float, _posicion: float = 0) -> str:
    """Acorta cantidades grandes para evitar ejes difíciles de leer."""
    if abs(valor) >= 1_000_000_000:
        return f"{valor / 1_000_000_000:.1f} mil M"
    if abs(valor) >= 1_000_000:
        return f"{valor / 1_000_000:.1f} M"
    if abs(valor) >= 1_000:
        return f"{valor / 1_000:.1f} mil"
    return f"{valor:g}"


def guardar_barras(datos: pd.DataFrame, categoria: str, valor: str,
                    titulo: str, xlabel: str, archivo: str, color: str,
                    porcentaje: bool = False) -> None:
    """Guarda una gráfica horizontal ordenada y etiquetada."""
    datos = datos.sort_values(valor)
    fig, ax = plt.subplots(figsize=(11, 7))
    barras = ax.barh(datos[categoria], datos[valor], color=color)
    ax.set_title(titulo, fontweight="bold", pad=14)
    ax.set_xlabel(xlabel)
    ax.grid(axis="x", alpha=.25)
    ax.set_axisbelow(True)
    if porcentaje:
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.1f}%"))
        etiquetas = [f"{x:.1f}%" for x in datos[valor]]
    else:
        ax.xaxis.set_major_formatter(FuncFormatter(formato_compacto))
        etiquetas = [formato_compacto(x) for x in datos[valor]]
    ax.bar_label(barras, labels=etiquetas, padding=3, fontsize=8)
    ax.margins(x=.15)
    fig.tight_layout()
    fig.savefig(FIG_DIR / archivo, dpi=180, bbox_inches="tight")
    plt.close(fig)


def generar_graficas(df: pd.DataFrame, cultivos: pd.DataFrame,
                     estados: pd.DataFrame) -> None:
    """Genera cinco visualizaciones analíticas."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    guardar_barras(cultivos.nlargest(TOP_N, "Volumen_produccion"),
                   "Nomcultivo", "Volumen_produccion",
                   f"Top {TOP_N} cultivos por volumen — 2025",
                   "Volumen de producción (toneladas)",
                   "01_top_cultivos_volumen.png", "#2a9d8f")
    guardar_barras(cultivos.nlargest(TOP_N, "Valor_produccion"),
                   "Nomcultivo", "Valor_produccion",
                   f"Top {TOP_N} cultivos por valor — 2025",
                   "Valor de producción (pesos)",
                   "02_top_cultivos_valor.png", "#e9c46a")
    guardar_barras(estados.nlargest(TOP_N, "Valor_produccion"),
                   "Nomestado", "Valor_produccion",
                   f"Top {TOP_N} estados por valor — 2025",
                   "Valor de producción (pesos)",
                   "03_top_estados_valor.png", "#457b9d")
    tasas = estados.dropna(subset=["Tasa_siniestro"]).nlargest(
        TOP_N, "Tasa_siniestro")
    guardar_barras(tasas, "Nomestado", "Tasa_siniestro",
                   f"Top {TOP_N} estados por superficie siniestrada — 2025",
                   "Porcentaje de la superficie sembrada",
                   "04_estados_tasa_siniestro.png", "#e76f51", True)

    puntos = df.loc[(df["Cosechada"] > 0) & (df["Volumenproduccion"] > 0),
                    ["Cosechada", "Volumenproduccion"]].dropna()
    if not puntos.empty:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.scatter(puntos["Cosechada"], puntos["Volumenproduccion"],
                   alpha=.25, s=14, color="#264653", edgecolors="none")
        ax.set(xscale="log", yscale="log",
               title="Superficie cosechada vs. volumen de producción — 2025",
               xlabel="Superficie cosechada (ha, escala logarítmica)",
               ylabel="Volumen de producción (t, escala logarítmica)")
        ax.grid(alpha=.2, which="both")
        fig.tight_layout()
        fig.savefig(FIG_DIR / "05_cosechada_vs_produccion.png", dpi=180)
        plt.close(fig)


def analizar(ruta: Path = CSV_PATH) -> None:
    """Ejecuta el flujo completo; también puede importarse desde otro módulo."""
    df = cargar_datos(ruta)
    mostrar_reporte(df)
    cultivos, estados = crear_resumenes(df)
    generar_graficas(df, cultivos, estados)
    print(f"\nTablas guardadas en: {OUTPUT_DIR}")
    print(f"Gráficas guardadas en: {FIG_DIR}")
    print("Exploración agrícola 2025 completada.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=CSV_PATH,
                        help="Ruta del CSV agrícola.")
    parser.add_argument("--descargar", action="store_true",
                        help="Descarga y reemplaza el CSV antes del análisis.")
    args = parser.parse_args()
    ruta = args.csv.resolve()
    if args.descargar:
        descargar_csv(ruta)
    analizar(ruta)


if __name__ == "__main__":
    main()
