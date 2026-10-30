"""Visualizaciones reutilizables para el proyecto agronómico."""

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

from proyecto_agronomia.config import FIGURES_DIR


COLUMNAS_AGRICOLAS = {
    "cvegeo",
    "Anio",
    "Nomcultivo",
    "Nomcicloproductivo",
    "Cosechada",
}

COLUMNAS_CLIMA_MENSUAL = {
    "cvegeo",
    "anio",
    "mes",
    "temperatura_media_mes_c",
    "precipitacion_mes_mm",
}

NOMBRES_MESES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

GRUPOS_SUELO_WRB = {
    "AC": "Acrisol", "AL": "Alisol", "AN": "Andosol", "AT": "Anthrosol",
    "AR": "Arenosol", "CL": "Calcisol", "CM": "Cambisol", "CH": "Chernozem",
    "CR": "Cryosol", "DU": "Durisol", "FR": "Ferralsol", "FL": "Fluvisol",
    "GL": "Gleysol", "GY": "Gypsisol", "HS": "Histosol", "KS": "Kastanozem",
    "LP": "Leptosol", "LX": "Lixisol", "LV": "Luvisol", "NT": "Nitisol",
    "PH": "Phaeozem", "PL": "Planosol", "PT": "Plinthosol", "PZ": "Podzol",
    "RG": "Regosol", "RT": "Retisol", "SC": "Solonchak", "SN": "Solonetz",
    "ST": "Stagnosol", "TC": "Technosol", "UM": "Umbrisol", "VR": "Vertisol",
}


def crear_mapa_edafologia(
    edafologia: gpd.GeoDataFrame,
    columna: str = "Grupo1",
    titulo: str | None = None,
    figsize: tuple[int, int] = (14, 10),
):
    """Grafica las unidades edafológicas y devuelve figura, eje y capa preparada."""
    if not isinstance(edafologia, gpd.GeoDataFrame):
        raise TypeError("edafologia debe ser un GeoDataFrame.")
    if columna not in edafologia.columns:
        raise KeyError(f"La capa edafológica no contiene la columna {columna!r}.")
    if edafologia.crs is None:
        raise ValueError("La capa edafológica no tiene un CRS definido.")
    if edafologia.empty:
        raise ValueError("La capa edafológica está vacía.")

    mapa = edafologia[[columna, "geometry"]].copy()
    codigos = mapa[columna].astype("string").str.strip().fillna("N")
    sin_clasificacion = codigos.isin(["", "N", "N/A", "NA"])
    codigos = codigos.mask(sin_clasificacion, "Sin clasificación")
    mapa["categoria_edafologica"] = codigos

    categorias = sorted(c for c in codigos.unique() if c != "Sin clasificación")
    colores_disponibles = list(plt.get_cmap("tab20").colors) + list(
        plt.get_cmap("tab20b").colors
    )
    paleta = {
        categoria: colores_disponibles[indice % len(colores_disponibles)]
        for indice, categoria in enumerate(categorias)
    }
    paleta["Sin clasificación"] = (0.80, 0.80, 0.80, 1)

    fig, ax = plt.subplots(figsize=figsize)
    mapa.plot(
        ax=ax,
        color=mapa["categoria_edafologica"].map(paleta),
        edgecolor="white",
        linewidth=0.03,
    )
    ax.set_axis_off()
    ax.set_title(
        titulo or "Grupos de suelo de México · INEGI Serie III",
        fontsize=16,
    )

    categorias_presentes = categorias + (
        ["Sin clasificación"] if "Sin clasificación" in set(codigos) else []
    )
    leyenda = []
    for categoria in categorias_presentes:
        etiqueta = (
            f"{categoria} · {GRUPOS_SUELO_WRB.get(categoria, 'Grupo no documentado')}"
            if categoria != "Sin clasificación"
            else categoria
        )
        leyenda.append(Patch(facecolor=paleta[categoria], label=etiqueta))
    ax.legend(
        handles=leyenda,
        title="Grupo principal WRB",
        loc="center left",
        bbox_to_anchor=(1.01, 0.5),
        frameon=False,
        fontsize=8,
        ncol=2 if len(leyenda) > 20 else 1,
    )
    fig.tight_layout()
    return fig, ax, mapa


def crear_heatmap_participacion(
    tabla: pd.DataFrame,
    titulo: str,
    etiqueta_color: str = "Participación (%)",
    figsize: tuple[int, int] = (15, 9),
):
    """Grafica una matriz numérica con sus categorías en ambos ejes."""
    if tabla.empty:
        raise ValueError("La tabla para el heatmap está vacía.")
    valores = tabla.apply(pd.to_numeric, errors="coerce")
    fig, ax = plt.subplots(figsize=figsize)
    imagen = ax.imshow(valores.fillna(0), aspect="auto", cmap="YlGnBu")
    ax.set_xticks(range(len(valores.columns)), valores.columns, rotation=55, ha="right")
    ax.set_yticks(range(len(valores.index)), valores.index)
    ax.set_title(titulo, fontsize=15)
    barra = fig.colorbar(imagen, ax=ax, fraction=0.025, pad=0.02)
    barra.set_label(etiqueta_color)
    fig.tight_layout()
    return fig, ax


def crear_dispersion_con_tendencia(
    datos: pd.DataFrame,
    x: str,
    y: str,
    titulo: str,
    etiqueta_x: str | None = None,
    etiqueta_y: str | None = None,
    bins: int = 10,
    figsize: tuple[int, int] = (10, 6),
):
    """Grafica observaciones y una tendencia robusta basada en medianas por cuantiles."""
    faltantes = {x, y} - set(datos.columns)
    if faltantes:
        raise KeyError(f"Faltan columnas para la dispersión: {sorted(faltantes)}")
    muestra = datos[[x, y]].apply(pd.to_numeric, errors="coerce").dropna()
    if muestra.empty:
        raise ValueError("No hay observaciones válidas para la dispersión.")

    fig, ax = plt.subplots(figsize=figsize)
    ax.scatter(muestra[x], muestra[y], s=9, alpha=0.12, color="#31688e", edgecolors="none")
    if muestra[x].nunique() > 1:
        muestra["intervalo"] = pd.qcut(
            muestra[x], q=min(bins, muestra[x].nunique()), duplicates="drop"
        )
        tendencia = muestra.groupby("intervalo", observed=True).agg(
            x_mediana=(x, "median"),
            y_mediana=(y, "median"),
        )
        ax.plot(
            tendencia["x_mediana"],
            tendencia["y_mediana"],
            color="#d1495b",
            marker="o",
            linewidth=2.2,
            label="Mediana por cuantiles",
        )
        ax.legend(frameon=False)
    if muestra[y].min() < 0 < muestra[y].max():
        ax.axhline(0, color="0.45", linewidth=0.8, linestyle="--")
    ax.set_title(titulo, fontsize=14)
    ax.set_xlabel(etiqueta_x or x)
    ax.set_ylabel(etiqueta_y or y)
    fig.tight_layout()
    return fig, ax


def preparar_geometrias_municipales(
    municipios: gpd.GeoDataFrame,
    tolerancia_m: float | None = 1_000,
) -> gpd.GeoDataFrame:
    """Normaliza la clave municipal y simplifica geometrías para graficar rápido."""
    if "cvegeo" not in municipios.columns:
        raise KeyError("La capa municipal debe contener la columna 'cvegeo'.")
    if municipios.crs is None:
        raise ValueError("La capa municipal no tiene un CRS definido.")

    resultado = municipios[["cvegeo", "geometry"]].copy()
    resultado["cvegeo"] = resultado["cvegeo"].astype("string").str.zfill(5)
    resultado = resultado.drop_duplicates("cvegeo")

    if tolerancia_m is not None and tolerancia_m > 0:
        resultado = resultado.to_crs(epsg=6372)
        resultado["geometry"] = resultado.geometry.simplify(
            tolerancia_m,
            preserve_topology=True,
        )

    return resultado


def preparar_cultivo_predominante(
    agricultura_clima: pd.DataFrame,
    anio: int | None = None,
    ciclo: str | None = None,
    cultivos_principales: list[str] | None = None,
    top_n: int = 10,
) -> pd.DataFrame:
    """Obtiene el cultivo con mayor superficie cosechada por municipio."""
    faltantes = COLUMNAS_AGRICOLAS - set(agricultura_clima.columns)
    if faltantes:
        raise KeyError(f"Faltan columnas requeridas: {sorted(faltantes)}")
    if top_n < 1:
        raise ValueError("top_n debe ser mayor que cero.")

    datos = agricultura_clima.copy()
    datos["cvegeo"] = datos["cvegeo"].astype("string").str.zfill(5)
    datos["Cosechada"] = pd.to_numeric(datos["Cosechada"], errors="coerce").fillna(0)

    if anio is not None:
        datos = datos.loc[datos["Anio"].eq(anio)]
    if ciclo is not None:
        datos = datos.loc[datos["Nomcicloproductivo"].eq(ciclo)]
    if datos.empty:
        raise ValueError(f"No hay datos para año={anio!r} y ciclo={ciclo!r}.")

    cosecha = (
        datos.groupby(["cvegeo", "Nomcultivo"], as_index=False, observed=True)["Cosechada"]
        .sum()
        .rename(columns={"Cosechada": "superficie_cosechada_ha"})
    )
    cosecha = cosecha.loc[cosecha["superficie_cosechada_ha"].gt(0)]

    if cultivos_principales is None:
        cultivos_principales = (
            cosecha.groupby("Nomcultivo", observed=True)["superficie_cosechada_ha"]
            .sum()
            .nlargest(top_n)
            .index.tolist()
        )

    predominante = (
        cosecha.sort_values(
            ["cvegeo", "superficie_cosechada_ha", "Nomcultivo"],
            ascending=[True, False, True],
        )
        .drop_duplicates("cvegeo")
        .rename(columns={"Nomcultivo": "cultivo_predominante"})
    )
    predominante["categoria_cultivo"] = predominante["cultivo_predominante"].where(
        predominante["cultivo_predominante"].isin(cultivos_principales),
        "Otros",
    )
    return predominante.reset_index(drop=True)


def _resumen_climatico_municipal(
    agricultura_clima: pd.DataFrame,
    anio: int,
) -> pd.DataFrame:
    """Extrae una observación climática por municipio y año."""
    columnas = ["cvegeo", "temperatura_media_c", "precipitacion_anual_mm"]
    clima = agricultura_clima.loc[agricultura_clima["Anio"].eq(anio), columnas].copy()
    clima["cvegeo"] = clima["cvegeo"].astype("string").str.zfill(5)
    return clima.groupby("cvegeo", as_index=False).agg(
        temperatura_media_c=("temperatura_media_c", "mean"),
        precipitacion_anual_mm=("precipitacion_anual_mm", "mean"),
    )


def _paleta_cultivos(cultivos: list[str]) -> dict[str, tuple]:
    """Crea colores estables para una lista de cultivos."""
    mapa = plt.get_cmap("tab20")
    paleta = {cultivo: mapa(indice % mapa.N) for indice, cultivo in enumerate(cultivos)}
    paleta["Otros"] = (0.55, 0.55, 0.55, 1)
    return paleta


def crear_mapa_cultivos(
    agricultura_clima: pd.DataFrame,
    municipios: gpd.GeoDataFrame,
    anio: int,
    ciclo: str | None = None,
    top_n: int = 10,
    figsize: tuple[int, int] = (13, 9),
):
    """Crea un mapa del cultivo predominante por superficie cosechada."""
    cultivos = preparar_cultivo_predominante(
        agricultura_clima,
        anio=anio,
        ciclo=ciclo,
        top_n=top_n,
    )
    categorias = (
        cultivos.groupby("categoria_cultivo")["superficie_cosechada_ha"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )
    paleta = _paleta_cultivos([valor for valor in categorias if valor != "Otros"])

    mapa = municipios.merge(cultivos, on="cvegeo", how="left", validate="one_to_one")
    colores = mapa["categoria_cultivo"].map(paleta).fillna("#eeeeee")

    fig, ax = plt.subplots(figsize=figsize)
    mapa.plot(ax=ax, color=colores, edgecolor="white", linewidth=0.08)
    ax.set_axis_off()
    ciclo_titulo = ciclo if ciclo is not None else "todos los ciclos"
    ax.set_title(f"Cultivo predominante por municipio · {anio}\n{ciclo_titulo}", fontsize=16)

    leyenda = [Patch(facecolor=paleta[c], label=c) for c in categorias]
    leyenda.append(Patch(facecolor="#eeeeee", label="Sin producción registrada"))
    ax.legend(
        handles=leyenda,
        title="Mayor superficie cosechada",
        loc="lower left",
        bbox_to_anchor=(1.01, 0),
        frameon=False,
    )
    fig.tight_layout()
    return fig, ax, mapa


def crear_animacion_agricultura_clima(
    agricultura_clima: pd.DataFrame,
    municipios: gpd.GeoDataFrame,
    ruta_salida: str | Path = FIGURES_DIR / "agricultura_clima_2003_2025.gif",
    ciclo: str | None = None,
    top_n: int = 10,
    fps: int = 2,
    dpi: int = 110,
) -> Path:
    """Genera un GIF anual con cultivo predominante, temperatura y lluvia."""
    anios = sorted(agricultura_clima["Anio"].dropna().astype(int).unique())
    base = agricultura_clima
    if ciclo is not None:
        base = base.loc[base["Nomcicloproductivo"].eq(ciclo)]
    if base.empty:
        raise ValueError(f"No hay observaciones para el ciclo {ciclo!r}.")

    superficie_nacional = (
        base.assign(Cosechada=pd.to_numeric(base["Cosechada"], errors="coerce").fillna(0))
        .groupby("Nomcultivo", observed=True)["Cosechada"]
        .sum()
    )
    principales = superficie_nacional.nlargest(top_n).index.tolist()
    paleta = _paleta_cultivos(principales)

    norma_temperatura = Normalize(
        agricultura_clima["temperatura_media_c"].quantile(0.02),
        agricultura_clima["temperatura_media_c"].quantile(0.98),
    )
    norma_precipitacion = Normalize(
        0,
        agricultura_clima["precipitacion_anual_mm"].quantile(0.98),
    )

    fig, ejes = plt.subplots(1, 3, figsize=(19, 7))
    ciclo_titulo = ciclo if ciclo is not None else "todos los ciclos"

    def actualizar(anio: int):
        for eje in ejes:
            eje.clear()
            eje.set_axis_off()

        cultivos = preparar_cultivo_predominante(
            agricultura_clima,
            anio=anio,
            ciclo=ciclo,
            cultivos_principales=principales,
            top_n=top_n,
        )
        clima = _resumen_climatico_municipal(agricultura_clima, anio)
        mapa = municipios.merge(cultivos, on="cvegeo", how="left", validate="one_to_one")
        mapa = mapa.merge(clima, on="cvegeo", how="left", validate="one_to_one")

        colores = mapa["categoria_cultivo"].map(paleta).fillna("#eeeeee")
        mapa.plot(ax=ejes[0], color=colores, edgecolor="white", linewidth=0.05)
        mapa.plot(
            ax=ejes[1],
            column="temperatura_media_c",
            cmap="coolwarm",
            norm=norma_temperatura,
            missing_kwds={"color": "#eeeeee"},
            edgecolor="none",
        )
        mapa.plot(
            ax=ejes[2],
            column="precipitacion_anual_mm",
            cmap="Blues",
            norm=norma_precipitacion,
            missing_kwds={"color": "#eeeeee"},
            edgecolor="none",
        )
        ejes[0].set_title(f"Cultivo predominante\n{ciclo_titulo}")
        ejes[1].set_title("Temperatura media anual (°C)")
        ejes[2].set_title("Precipitación anual (mm)")
        fig.suptitle(f"Agricultura y clima en México · {anio}", fontsize=18)
        return ejes

    animacion = FuncAnimation(fig, actualizar, frames=anios, repeat=True)
    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    animacion.save(ruta_salida, writer=PillowWriter(fps=fps), dpi=dpi)
    plt.close(fig)
    return ruta_salida


def _validar_clima_mensual(clima_mensual: pd.DataFrame) -> pd.DataFrame:
    """Valida y normaliza el dataset climático mensual."""
    faltantes = COLUMNAS_CLIMA_MENSUAL - set(clima_mensual.columns)
    if faltantes:
        raise KeyError(f"Faltan columnas climáticas: {sorted(faltantes)}")

    datos = clima_mensual[list(COLUMNAS_CLIMA_MENSUAL)].copy()
    datos["cvegeo"] = datos["cvegeo"].astype("string").str.zfill(5)
    datos["anio"] = pd.to_numeric(datos["anio"], errors="raise").astype(int)
    datos["mes"] = pd.to_numeric(datos["mes"], errors="raise").astype(int)
    if not datos["mes"].between(1, 12).all():
        raise ValueError("La columna mes debe contener valores entre 1 y 12.")
    if datos.duplicated(["cvegeo", "anio", "mes"]).any():
        raise ValueError("Hay claves municipio-año-mes duplicadas.")
    return datos


def crear_mapa_clima_mensual(
    clima_mensual: pd.DataFrame,
    municipios: gpd.GeoDataFrame,
    anio: int,
    mes: int,
    limites_temperatura: tuple[float, float] | None = None,
    limites_precipitacion: tuple[float, float] | None = None,
    figsize: tuple[int, int] = (15, 7),
):
    """Crea mapas municipales de temperatura y precipitación para un mes."""
    datos = _validar_clima_mensual(clima_mensual)
    seleccion = datos.loc[datos["anio"].eq(anio) & datos["mes"].eq(mes)]
    if seleccion.empty:
        raise ValueError(f"No hay clima mensual para {anio}-{mes:02d}.")

    if limites_temperatura is None:
        limites_temperatura = (
            float(datos["temperatura_media_mes_c"].quantile(0.02)),
            float(datos["temperatura_media_mes_c"].quantile(0.98)),
        )
    if limites_precipitacion is None:
        limites_precipitacion = (
            0.0,
            float(datos["precipitacion_mes_mm"].quantile(0.98)),
        )

    mapa = municipios.merge(seleccion, on="cvegeo", how="left", validate="one_to_one")
    fig, ejes = plt.subplots(1, 2, figsize=figsize)
    norma_temperatura = Normalize(*limites_temperatura)
    norma_precipitacion = Normalize(*limites_precipitacion)
    mapa.plot(
        ax=ejes[0],
        column="temperatura_media_mes_c",
        cmap="coolwarm",
        norm=norma_temperatura,
        missing_kwds={"color": "#eeeeee"},
        edgecolor="none",
    )
    mapa.plot(
        ax=ejes[1],
        column="precipitacion_mes_mm",
        cmap="Blues",
        norm=norma_precipitacion,
        missing_kwds={"color": "#eeeeee"},
        edgecolor="none",
    )
    for eje in ejes:
        eje.set_axis_off()
    ejes[0].set_title("Temperatura media mensual (°C)")
    ejes[1].set_title("Precipitación mensual (mm)")
    fig.colorbar(
        ScalarMappable(norm=norma_temperatura, cmap="coolwarm"),
        ax=ejes[0],
        shrink=0.7,
    )
    fig.colorbar(
        ScalarMappable(norm=norma_precipitacion, cmap="Blues"),
        ax=ejes[1],
        shrink=0.7,
    )
    fig.suptitle(f"Clima municipal en México · {NOMBRES_MESES[mes]} {anio}", fontsize=16)
    fig.tight_layout()
    return fig, ejes, mapa


def crear_animacion_clima_mensual(
    clima_mensual: pd.DataFrame,
    municipios: gpd.GeoDataFrame,
    ruta_salida: str | Path = FIGURES_DIR / "clima_mensual_mexico_2003_2025.gif",
    anio_inicial: int = 2003,
    anio_final: int = 2025,
    fps: int = 6,
    dpi: int = 90,
) -> Path:
    """Genera un GIF mensual nacional de temperatura y precipitación."""
    datos = _validar_clima_mensual(clima_mensual)
    datos = datos.loc[datos["anio"].between(anio_inicial, anio_final)].copy()
    if datos.empty:
        raise ValueError("No hay observaciones en el intervalo solicitado.")

    fotogramas = sorted(datos[["anio", "mes"]].drop_duplicates().itertuples(index=False))
    norma_temperatura = Normalize(
        float(datos["temperatura_media_mes_c"].quantile(0.02)),
        float(datos["temperatura_media_mes_c"].quantile(0.98)),
    )
    norma_precipitacion = Normalize(
        0.0,
        float(datos["precipitacion_mes_mm"].quantile(0.98)),
    )

    fig, ejes = plt.subplots(1, 2, figsize=(15, 7))
    fig.colorbar(
        ScalarMappable(norm=norma_temperatura, cmap="coolwarm"),
        ax=ejes[0],
        shrink=0.7,
        label="°C",
    )
    fig.colorbar(
        ScalarMappable(norm=norma_precipitacion, cmap="Blues"),
        ax=ejes[1],
        shrink=0.7,
        label="mm",
    )

    def actualizar(fecha):
        anio, mes = int(fecha.anio), int(fecha.mes)
        for eje in ejes:
            eje.clear()
            eje.set_axis_off()
        seleccion = datos.loc[datos["anio"].eq(anio) & datos["mes"].eq(mes)]
        mapa = municipios.merge(
            seleccion,
            on="cvegeo",
            how="left",
            validate="one_to_one",
        )
        mapa.plot(
            ax=ejes[0],
            column="temperatura_media_mes_c",
            cmap="coolwarm",
            norm=norma_temperatura,
            missing_kwds={"color": "#eeeeee"},
            edgecolor="none",
        )
        mapa.plot(
            ax=ejes[1],
            column="precipitacion_mes_mm",
            cmap="Blues",
            norm=norma_precipitacion,
            missing_kwds={"color": "#eeeeee"},
            edgecolor="none",
        )
        media_temperatura = seleccion["temperatura_media_mes_c"].mean()
        media_precipitacion = seleccion["precipitacion_mes_mm"].mean()
        ejes[0].set_title(f"Temperatura media · {media_temperatura:.1f} °C")
        ejes[1].set_title(f"Precipitación media municipal · {media_precipitacion:.1f} mm")
        fig.suptitle(f"Clima en México · {NOMBRES_MESES[mes]} {anio}", fontsize=17)
        return ejes

    animacion = FuncAnimation(
        fig,
        actualizar,
        frames=fotogramas,
        repeat=True,
        cache_frame_data=False,
    )
    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    animacion.save(ruta_salida, writer=PillowWriter(fps=fps), dpi=dpi)
    plt.close(fig)
    return ruta_salida
