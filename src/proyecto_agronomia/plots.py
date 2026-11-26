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
from scipy.stats import chi2_contingency

from proyecto_agronomia.config import FIGURES_DIR
from datasets.edafologia import GRUPOS_SUELO_WRB


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


def crear_matriz_correlacion_agricola(
    agricultura: pd.DataFrame,
    columnas: list[str] | None = None,
    metodo: str = "spearman",
    minimo_observaciones: int = 100,
    ruta_salida: str | Path | None = None,
):
    """Grafica correlaciones productivas, climaticas, edafologicas e historicas.

    Spearman es el metodo predeterminado porque resume asociaciones monotonas y
    es menos sensible a valores extremos y escalas distintas que Pearson.
    """
    columnas = columnas or [
        "Sembrada", "Cosechada", "Siniestrada", "Volumenproduccion",
        "Rendimiento", "Preciomediorural", "Valorproduccion",
        "temperatura_media_ciclo_c", "precipitacion_ciclo_mm",
        "grupo_suelo_dominante_pct", "grupos_suelo_n",
        "rendimiento_anio_anterior", "rendimiento_hist_media",
        "rendimiento_hist_cv",
    ]
    disponibles = [columna for columna in columnas if columna in agricultura.columns]
    if len(disponibles) < 2:
        raise KeyError("No hay suficientes columnas numericas para correlacionar.")
    if metodo not in {"pearson", "spearman", "kendall"}:
        raise ValueError("metodo debe ser 'pearson', 'spearman' o 'kendall'.")

    datos = (
        agricultura[disponibles]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
    )
    cobertura = datos.notna().sum().rename("observaciones").to_frame()
    correlacion = datos.corr(method=metodo, min_periods=minimo_observaciones)
    etiquetas = {
        "Sembrada": "Superficie sembrada",
        "Cosechada": "Superficie cosechada",
        "Siniestrada": "Superficie siniestrada",
        "Volumenproduccion": "Produccion",
        "Rendimiento": "Rendimiento",
        "Preciomediorural": "Precio medio rural",
        "Valorproduccion": "Valor de produccion",
        "temperatura_media_ciclo_c": "Temperatura del ciclo",
        "precipitacion_ciclo_mm": "Precipitacion del ciclo",
        "grupo_suelo_dominante_pct": "Cobertura del suelo dominante",
        "grupos_suelo_n": "Diversidad de grupos de suelo",
        "rendimiento_anio_anterior": "Rendimiento previo",
        "rendimiento_hist_media": "Rendimiento historico",
        "rendimiento_hist_cv": "Variabilidad historica (CV)",
    }
    nombres = [etiquetas.get(columna, columna) for columna in correlacion.columns]
    mascara = np.triu(np.ones(correlacion.shape, dtype=bool), k=1)
    valores = np.ma.array(correlacion.to_numpy(), mask=mascara)
    lado = max(10, len(disponibles) * 0.78)
    fig, ax = plt.subplots(figsize=(lado, lado * 0.88))
    imagen = ax.imshow(valores, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(nombres)), nombres, rotation=52, ha="right")
    ax.set_yticks(range(len(nombres)), nombres)
    ax.set_title(f"Matriz de correlacion agricola · {metodo.capitalize()}", fontsize=16)
    for fila in range(len(nombres)):
        for columna in range(fila + 1):
            valor = correlacion.iloc[fila, columna]
            texto = "—" if pd.isna(valor) else f"{valor:.2f}"
            color = "white" if pd.notna(valor) and abs(valor) >= 0.55 else "#17372c"
            ax.text(columna, fila, texto, ha="center", va="center", fontsize=8, color=color)
    barra = fig.colorbar(imagen, ax=ax, fraction=0.035, pad=0.025)
    barra.set_label(f"Correlacion de {metodo.capitalize()} (−1 a 1)")
    fig.text(
        0.01, 0.01,
        "Asociacion no implica causalidad. Produccion, superficie y rendimiento "
        "comparten definiciones contables.",
        fontsize=9, color="#6c786f",
    )
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    if ruta_salida is not None:
        ruta_salida = Path(ruta_salida)
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(ruta_salida, dpi=180, bbox_inches="tight")
    return fig, ax, correlacion, cobertura


def crear_selector_matriz_correlacion(
    agricultura: pd.DataFrame,
    unidad: str = "Tonelada",
    minimo_registros: int = 300,
    minimo_observaciones_correlacion: int = 100,
    metodo: str = "spearman",
):
    """Crea un selector Jupyter de matrices de correlacion por cultivo."""
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as error:
        raise ImportError(
            "El selector requiere ipywidgets. Instala dependencias y reinicia el kernel."
        ) from error

    requeridas = {"Nomcultivo", "Nomunidad"}
    faltantes = requeridas - set(agricultura.columns)
    if faltantes:
        raise KeyError(f"Faltan columnas para el selector: {sorted(faltantes)}")
    base = agricultura.loc[agricultura["Nomunidad"].eq(unidad)].copy()
    cobertura = (
        base.groupby("Nomcultivo", observed=True)
        .size().loc[lambda serie: serie.ge(minimo_registros)]
        .sort_values(ascending=False)
    )
    if cobertura.empty:
        raise ValueError("No hay cultivos con cobertura suficiente para el selector.")
    opciones = [
        (f"{cultivo} · {registros:,} registros", cultivo)
        for cultivo, registros in cobertura.items()
    ]
    selector = widgets.Dropdown(
        options=opciones,
        value=opciones[0][1],
        description="Cultivo:",
        layout=widgets.Layout(width="560px"),
        style={"description_width": "70px"},
    )
    salida = widgets.Output()

    def actualizar(*_):
        with salida:
            salida.clear_output(wait=True)
            cultivo = selector.value
            datos = base.loc[base["Nomcultivo"].eq(cultivo)]
            fig, ax, correlacion, cobertura_variables = crear_matriz_correlacion_agricola(
                datos,
                metodo=metodo,
                minimo_observaciones=minimo_observaciones_correlacion,
            )
            ax.set_title(
                f"Matriz de correlacion · {cultivo} · {metodo.capitalize()}",
                fontsize=16,
            )
            plt.show()
            plt.close(fig)
            variables_utiles = int(
                cobertura_variables["observaciones"]
                .ge(minimo_observaciones_correlacion).sum()
            )
            print(
                f"{cultivo}: {len(datos):,} registros; "
                f"{variables_utiles} variables con al menos "
                f"{minimo_observaciones_correlacion:,} observaciones."
            )

    selector.observe(actualizar, names="value")
    actualizar()
    return widgets.VBox([
        widgets.HTML(
            "<b>Correlaciones dentro de cada cultivo</b><br>"
            "La escala de color va de −1 a 1; asociación no implica causalidad."
        ),
        selector,
        salida,
    ])


def _v_cramer(primera: pd.Series, segunda: pd.Series) -> float:
    """Calcula V de Cramer corregida entre dos variables categoricas."""
    tabla = pd.crosstab(primera, segunda)
    if tabla.shape[0] < 2 or tabla.shape[1] < 2:
        return np.nan
    chi2 = chi2_contingency(tabla, correction=False)[0]
    n = tabla.to_numpy().sum()
    filas, columnas = tabla.shape
    phi2 = chi2 / n
    phi2_corregido = max(0, phi2 - ((columnas - 1) * (filas - 1)) / (n - 1))
    filas_corregidas = filas - ((filas - 1) ** 2) / (n - 1)
    columnas_corregidas = columnas - ((columnas - 1) ** 2) / (n - 1)
    denominador = min(columnas_corregidas - 1, filas_corregidas - 1)
    return np.sqrt(phi2_corregido / denominador) if denominador > 0 else np.nan


def _razon_correlacion(categorias: pd.Series, valores: pd.Series) -> float:
    """Calcula eta para una variable categorica y otra numerica."""
    codigos, _ = pd.factorize(categorias, sort=False)
    valores = pd.to_numeric(valores, errors="coerce").to_numpy(dtype=float)
    media = np.nanmean(valores)
    denominador = np.nansum((valores - media) ** 2)
    if denominador <= 0:
        return np.nan
    numerador = 0.0
    for codigo in np.unique(codigos[codigos >= 0]):
        grupo = valores[codigos == codigo]
        grupo = grupo[np.isfinite(grupo)]
        if grupo.size:
            numerador += grupo.size * (grupo.mean() - media) ** 2
    return float(np.sqrt(max(0.0, numerador / denominador)))


def crear_matriz_asociacion_clima_suelo(
    agricultura: pd.DataFrame,
    minimo_observaciones: int = 100,
    ruta_salida: str | Path | None = None,
):
    """Relaciona rendimiento, clima y edafologia sin ordinalizar categorias."""
    numericas = [
        "Rendimiento", "temperatura_media_ciclo_c", "precipitacion_ciclo_mm",
        "grupo_suelo_dominante_pct", "textura_dominante_pct",
        "grupos_suelo_n", "rendimiento_hist_cv",
    ]
    categoricas = [
        "grupo_suelo_dominante", "textura_dominante",
        "Nomcicloproductivo", "Nommodalidad",
    ]
    numericas = [columna for columna in numericas if columna in agricultura.columns]
    categoricas = [columna for columna in categoricas if columna in agricultura.columns]
    columnas = [*numericas, *categoricas]
    if len(columnas) < 2:
        raise KeyError("No hay suficientes variables climaticas y edafologicas.")
    datos = agricultura[columnas].copy()
    datos[numericas] = datos[numericas].apply(pd.to_numeric, errors="coerce")
    matriz = pd.DataFrame(np.nan, index=columnas, columns=columnas, dtype=float)
    cobertura = pd.DataFrame(0, index=columnas, columns=columnas, dtype=int)
    for indice, primera in enumerate(columnas):
        for segunda in columnas[: indice + 1]:
            pareja = datos[[primera, segunda]].dropna()
            n = len(pareja)
            cobertura.loc[primera, segunda] = cobertura.loc[segunda, primera] = n
            if primera == segunda:
                valor = 1.0 if n >= minimo_observaciones else np.nan
            elif n < minimo_observaciones:
                valor = np.nan
            elif primera in numericas and segunda in numericas:
                valor = abs(pareja[primera].corr(pareja[segunda], method="spearman"))
            elif primera in categoricas and segunda in categoricas:
                valor = _v_cramer(pareja[primera], pareja[segunda])
            else:
                categorica = primera if primera in categoricas else segunda
                numerica = segunda if primera in categoricas else primera
                valor = _razon_correlacion(pareja[categorica], pareja[numerica])
            matriz.loc[primera, segunda] = matriz.loc[segunda, primera] = valor

    etiquetas = {
        "Rendimiento": "Rendimiento", "temperatura_media_ciclo_c": "Temperatura",
        "precipitacion_ciclo_mm": "Precipitacion",
        "grupo_suelo_dominante_pct": "% suelo dominante",
        "textura_dominante_pct": "% textura dominante",
        "grupos_suelo_n": "Diversidad de suelos",
        "rendimiento_hist_cv": "Variabilidad historica",
        "grupo_suelo_dominante": "Grupo de suelo", "textura_dominante": "Textura",
        "Nomcicloproductivo": "Ciclo productivo", "Nommodalidad": "Modalidad",
    }
    nombres = [etiquetas.get(columna, columna) for columna in columnas]
    mascara = np.triu(np.ones(matriz.shape, dtype=bool), k=1)
    valores = np.ma.array(matriz.to_numpy(), mask=mascara)
    lado = max(10, len(columnas) * 0.72)
    fig, ax = plt.subplots(figsize=(lado, lado * 0.9))
    imagen = ax.imshow(valores, cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_xticks(range(len(nombres)), nombres, rotation=52, ha="right")
    ax.set_yticks(range(len(nombres)), nombres)
    ax.set_title("Asociacion entre rendimiento, clima y suelo", fontsize=16)
    for fila in range(len(nombres)):
        for columna in range(fila + 1):
            valor = matriz.iloc[fila, columna]
            ax.text(
                columna, fila, "—" if pd.isna(valor) else f"{valor:.2f}",
                ha="center", va="center", fontsize=8,
                color="white" if pd.notna(valor) and valor >= 0.55 else "#17372c",
            )
    barra = fig.colorbar(imagen, ax=ax, fraction=0.035, pad=0.025)
    barra.set_label("Fuerza de asociacion (0 a 1)")
    fig.text(
        0.01, 0.01,
        "Spearman absoluto: numerica–numerica · eta: numerica–categorica · "
        "V de Cramer: categorica–categorica.",
        fontsize=9, color="#6c786f",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    if ruta_salida is not None:
        ruta_salida = Path(ruta_salida)
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(ruta_salida, dpi=180, bbox_inches="tight")
    return fig, ax, matriz, cobertura


def crear_selector_asociacion_clima_suelo(
    agricultura: pd.DataFrame,
    unidad: str = "Tonelada",
    minimo_registros: int = 300,
    minimo_observaciones: int = 100,
):
    """Selector Jupyter de asociaciones mixtas por cultivo."""
    try:
        import ipywidgets as widgets
    except ImportError as error:
        raise ImportError("El selector requiere ipywidgets.") from error
    base = agricultura.loc[agricultura["Nomunidad"].eq(unidad)].copy()
    cobertura = (
        base.groupby("Nomcultivo", observed=True).size()
        .loc[lambda serie: serie.ge(minimo_registros)].sort_values(ascending=False)
    )
    opciones = [(f"{cultivo} · {n:,} registros", cultivo) for cultivo, n in cobertura.items()]
    if not opciones:
        raise ValueError("No hay cultivos con cobertura suficiente.")
    selector = widgets.Dropdown(
        options=opciones, value=opciones[0][1], description="Cultivo:",
        layout=widgets.Layout(width="560px"), style={"description_width": "70px"},
    )
    salida = widgets.Output()

    def actualizar(*_):
        with salida:
            salida.clear_output(wait=True)
            cultivo = selector.value
            datos = base.loc[base["Nomcultivo"].eq(cultivo)]
            fig, ax, _, _ = crear_matriz_asociacion_clima_suelo(
                datos, minimo_observaciones=minimo_observaciones,
            )
            ax.set_title(f"Rendimiento, clima y suelo · {cultivo}", fontsize=16)
            plt.show()
            plt.close(fig)
            print(f"{cultivo}: {len(datos):,} registros analizados.")

    selector.observe(actualizar, names="value")
    actualizar()
    return widgets.VBox([
        widgets.HTML(
            "<b>Asociaciones mixtas por cultivo</b><br>"
            "Valores cercanos a 1 indican mayor asociación; no implican causalidad."
        ),
        selector, salida,
    ])


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
def plot_varianza_reduccion(reductor):
    """Grafica la varianza acumulada de una reduccion tipo PCA/SVD."""
    import matplotlib.pyplot as plt
    import numpy as np

    acumulada = np.cumsum(reductor.explained_variance_ratio_) * 100
    figura, eje = plt.subplots(figsize=(9, 5))
    eje.plot(range(1, len(acumulada) + 1), acumulada, marker="o", markersize=3)
    eje.set(
        title="Varianza explicada acumulada por componentes",
        xlabel="Numero de componentes",
        ylabel="Varianza explicada acumulada (%)",
    )
    eje.grid(alpha=0.25)
    figura.tight_layout()
    return figura, eje


def _cultivo_dominante_por_superficie(
    escenarios: pd.DataFrame,
    columna_superficie: str,
) -> pd.DataFrame:
    """Resume el cultivo con mayor superficie de cada municipio."""
    requeridas = {"cvegeo", "Nomcultivo", columna_superficie}
    faltantes = requeridas - set(escenarios.columns)
    if faltantes:
        raise KeyError(f"Faltan columnas para el mapa: {sorted(faltantes)}")
    datos = escenarios[["cvegeo", "Nomcultivo", columna_superficie]].copy()
    datos["cvegeo"] = datos["cvegeo"].astype("string").str.zfill(5)
    datos[columna_superficie] = pd.to_numeric(
        datos[columna_superficie], errors="coerce"
    ).fillna(0)
    resumen = (
        datos.groupby(["cvegeo", "Nomcultivo"], as_index=False, observed=True)
        [columna_superficie].sum()
    )
    resumen = resumen.loc[resumen[columna_superficie].gt(0)]
    return (
        resumen.sort_values(
            ["cvegeo", columna_superficie, "Nomcultivo"],
            ascending=[True, False, True],
        )
        .drop_duplicates("cvegeo")
        .rename(columns={"Nomcultivo": "cultivo_dominante"})
        .reset_index(drop=True)
    )


def crear_mapa_redistribucion_cultivos(
    escenarios: pd.DataFrame,
    municipios: gpd.GeoDataFrame,
    escenario: str = "intermedio",
    ruta_salida: str | Path | None = (
        FIGURES_DIR / "redistribucion_cultivos_original_vs_intermedio.png"
    ),
    figsize: tuple[int, int] = (18, 9),
    dpi: int = 160,
):
    """Compara el cultivo dominante municipal antes y despues del intercambio."""
    columna_nueva = f"superficie_{escenario}_ha"
    if columna_nueva not in escenarios.columns:
        raise KeyError(f"No existe la superficie del escenario {escenario!r}.")
    geometrias = preparar_geometrias_municipales(municipios)
    original = _cultivo_dominante_por_superficie(
        escenarios, "superficie_base_ha"
    ).rename(columns={"cultivo_dominante": "cultivo_original"})
    nueva = _cultivo_dominante_por_superficie(
        escenarios, columna_nueva
    ).rename(columns={"cultivo_dominante": "cultivo_nuevo"})
    comparacion = original[["cvegeo", "cultivo_original"]].merge(
        nueva[["cvegeo", "cultivo_nuevo"]],
        on="cvegeo",
        how="outer",
        validate="one_to_one",
    )
    comparacion["cambio_dominante"] = (
        comparacion["cultivo_original"].notna()
        & comparacion["cultivo_nuevo"].notna()
        & comparacion["cultivo_original"].ne(comparacion["cultivo_nuevo"])
    )
    mapa = geometrias.merge(comparacion, on="cvegeo", how="left", validate="one_to_one")
    cultivos = sorted(set(
        comparacion["cultivo_original"].dropna()
    ) | set(comparacion["cultivo_nuevo"].dropna()))
    paleta = _paleta_cultivos(cultivos)

    fig, ejes = plt.subplots(1, 2, figsize=figsize)
    configuraciones = [
        ("cultivo_original", "Distribucion original · 2025"),
        ("cultivo_nuevo", f"Redistribucion · escenario {escenario}"),
    ]
    for eje, (columna, titulo) in zip(ejes, configuraciones):
        colores = mapa[columna].map(paleta).fillna("#eeeeee")
        mapa.plot(ax=eje, color=colores, edgecolor="white", linewidth=0.06)
        eje.set_axis_off()
        eje.set_title(titulo, fontsize=15)

    cambios = int(comparacion["cambio_dominante"].sum())
    fig.suptitle(
        f"Cultivo dominante por superficie municipal · {cambios:,} municipios cambian",
        fontsize=17,
    )
    leyenda = [Patch(facecolor=paleta[cultivo], label=cultivo) for cultivo in cultivos]
    leyenda.append(Patch(facecolor="#eeeeee", label="Sin superficie elegible"))
    fig.legend(
        handles=leyenda,
        title="Cultivo dominante",
        loc="lower center",
        bbox_to_anchor=(0.5, -0.01),
        ncol=min(4, max(1, len(leyenda))),
        frameon=False,
    )
    fig.tight_layout(rect=(0, 0.10, 1, 0.95))
    if ruta_salida is not None:
        ruta_salida = Path(ruta_salida)
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(ruta_salida, dpi=dpi, bbox_inches="tight")
    return fig, ejes, mapa, comparacion


def _preparar_dominantes_animacion(
    agricultura: pd.DataFrame,
    top_n: int,
    por_ciclo: bool,
) -> tuple[pd.DataFrame, list[int], list[str], dict]:
    """Precalcula cultivos dominantes y una paleta estable para los GIF."""
    requeridas = {
        "cvegeo", "Anio", "Nomcultivo", "Nomcicloproductivo", "Cosechada",
    }
    faltantes = requeridas - set(agricultura.columns)
    if faltantes:
        raise KeyError(f"Faltan columnas para la animacion: {sorted(faltantes)}")
    if top_n < 1:
        raise ValueError("top_n debe ser mayor que cero.")
    datos = agricultura[list(requeridas)].copy()
    datos["cvegeo"] = datos["cvegeo"].astype("string").str.zfill(5)
    datos["Anio"] = pd.to_numeric(datos["Anio"], errors="coerce")
    datos["Cosechada"] = pd.to_numeric(
        datos["Cosechada"], errors="coerce"
    ).fillna(0)
    datos = datos.loc[datos["Anio"].notna() & datos["Cosechada"].gt(0)].copy()
    datos["Anio"] = datos["Anio"].astype(int)
    cultivos = (
        datos.groupby("Nomcultivo", observed=True)["Cosechada"]
        .sum().nlargest(top_n).index.tolist()
    )
    claves = ["Anio", "cvegeo", "Nomcultivo"]
    if por_ciclo:
        claves.insert(2, "Nomcicloproductivo")
    resumen = (
        datos.groupby(claves, as_index=False, observed=True)["Cosechada"].sum()
    )
    orden = ["Anio"]
    if por_ciclo:
        orden.append("Nomcicloproductivo")
    orden += ["cvegeo", "Cosechada", "Nomcultivo"]
    ascendentes = [True] * (len(orden) - 2) + [False, True]
    dominantes = resumen.sort_values(orden, ascending=ascendentes)
    duplicados = ["Anio", "cvegeo"]
    if por_ciclo:
        duplicados.insert(1, "Nomcicloproductivo")
    dominantes = dominantes.drop_duplicates(duplicados)
    dominantes["categoria_cultivo"] = dominantes["Nomcultivo"].where(
        dominantes["Nomcultivo"].isin(cultivos), "Otros"
    )
    anios = sorted(dominantes["Anio"].unique().tolist())
    paleta = _paleta_cultivos(cultivos)
    return dominantes, anios, cultivos, paleta


def crear_animacion_cultivos_anual(
    agricultura: pd.DataFrame,
    municipios: gpd.GeoDataFrame,
    ruta_salida: str | Path = FIGURES_DIR / "cultivos_anual_2003_2025.gif",
    top_n: int = 12,
    fps: int = 2,
    dpi: int = 105,
) -> Path:
    """Genera un GIF anual del cultivo predominante por municipio."""
    geometrias = preparar_geometrias_municipales(municipios)
    dominantes, anios, cultivos, paleta = _preparar_dominantes_animacion(
        agricultura, top_n=top_n, por_ciclo=False
    )
    fig, ax = plt.subplots(figsize=(13, 9))
    leyenda = [Patch(facecolor=paleta[c], label=c) for c in cultivos]
    leyenda += [
        Patch(facecolor=paleta["Otros"], label="Otros"),
        Patch(facecolor="#eeeeee", label="Sin cosecha registrada"),
    ]

    def actualizar(anio):
        ax.clear()
        seleccion = dominantes.loc[
            dominantes["Anio"].eq(anio), ["cvegeo", "categoria_cultivo"]
        ]
        mapa = geometrias.merge(
            seleccion, on="cvegeo", how="left", validate="one_to_one"
        )
        colores = mapa["categoria_cultivo"].map(paleta).fillna("#eeeeee")
        mapa.plot(ax=ax, color=colores, edgecolor="white", linewidth=0.05)
        ax.set_axis_off()
        ax.set_title(f"Cultivo predominante por municipio · {anio}", fontsize=17)
        return [ax]

    animacion = FuncAnimation(
        fig, actualizar, frames=anios, repeat=True, cache_frame_data=False
    )
    fig.legend(
        handles=leyenda, title="Mayor superficie cosechada",
        loc="lower center", bbox_to_anchor=(0.5, 0.01), ncol=4,
        frameon=False, fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.13, 1, 1))
    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    animacion.save(ruta_salida, writer=PillowWriter(fps=fps), dpi=dpi)
    plt.close(fig)
    return ruta_salida


def crear_animacion_cultivos_por_ciclo(
    agricultura: pd.DataFrame,
    municipios: gpd.GeoDataFrame,
    ruta_salida: str | Path = FIGURES_DIR / "cultivos_ciclos_2003_2025.gif",
    ciclos: tuple[str, ...] = (
        "Otoño-Invierno", "Primavera-Verano", "Perennes",
    ),
    top_n: int = 12,
    fps: int = 2,
    dpi: int = 100,
) -> Path:
    """Genera un GIF anual comparando los tres ciclos productivos."""
    geometrias = preparar_geometrias_municipales(municipios)
    dominantes, anios, cultivos, paleta = _preparar_dominantes_animacion(
        agricultura, top_n=top_n, por_ciclo=True
    )
    fig, ejes = plt.subplots(1, len(ciclos), figsize=(19, 7))
    ejes = np.atleast_1d(ejes)
    leyenda = [Patch(facecolor=paleta[c], label=c) for c in cultivos]
    leyenda += [
        Patch(facecolor=paleta["Otros"], label="Otros"),
        Patch(facecolor="#eeeeee", label="Sin cosecha registrada"),
    ]

    def actualizar(anio):
        for eje, ciclo in zip(ejes, ciclos):
            eje.clear()
            seleccion = dominantes.loc[
                dominantes["Anio"].eq(anio)
                & dominantes["Nomcicloproductivo"].eq(ciclo),
                ["cvegeo", "categoria_cultivo"],
            ]
            mapa = geometrias.merge(
                seleccion, on="cvegeo", how="left", validate="one_to_one"
            )
            colores = mapa["categoria_cultivo"].map(paleta).fillna("#eeeeee")
            mapa.plot(ax=eje, color=colores, edgecolor="white", linewidth=0.04)
            eje.set_axis_off()
            eje.set_title(ciclo, fontsize=13)
        fig.suptitle(f"Cultivo predominante por ciclo productivo · {anio}", fontsize=17)
        return list(ejes)

    animacion = FuncAnimation(
        fig, actualizar, frames=anios, repeat=True, cache_frame_data=False
    )
    fig.legend(
        handles=leyenda, title="Mayor superficie cosechada",
        loc="lower center", bbox_to_anchor=(0.5, -0.01), ncol=5,
        frameon=False, fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.16, 1, 0.94))
    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    animacion.save(ruta_salida, writer=PillowWriter(fps=fps), dpi=dpi)
    plt.close(fig)
    return ruta_salida


def crear_mapa_redistribucion_por_ciclo(
    escenarios: pd.DataFrame,
    municipios: gpd.GeoDataFrame,
    escenario: str = "intermedio",
    ciclos: tuple[str, ...] = (
        "Otoño-Invierno", "Primavera-Verano", "Perennes",
    ),
    ruta_salida: str | Path | None = (
        FIGURES_DIR / "redistribucion_cultivos_por_ciclo_intermedio.png"
    ),
    figsize: tuple[int, int] = (20, 12),
    dpi: int = 160,
):
    """Compara cultivos dominantes originales y redistribuidos por ciclo."""
    columna_nueva = f"superficie_{escenario}_ha"
    requeridas = {
        "cvegeo", "Nomcultivo", "Nomcicloproductivo",
        "superficie_base_ha", columna_nueva,
    }
    faltantes = requeridas - set(escenarios.columns)
    if faltantes:
        raise KeyError(f"Faltan columnas para el mapa por ciclo: {sorted(faltantes)}")
    geometrias = preparar_geometrias_municipales(municipios)
    cultivos = sorted(escenarios["Nomcultivo"].dropna().unique().tolist())
    paleta = _paleta_cultivos(cultivos)
    fig, ejes = plt.subplots(2, len(ciclos), figsize=figsize)
    comparaciones = []

    for columna, ciclo in enumerate(ciclos):
        datos_ciclo = escenarios.loc[
            escenarios["Nomcicloproductivo"].eq(ciclo)
        ].copy()
        original = _cultivo_dominante_por_superficie(
            datos_ciclo, "superficie_base_ha"
        ).rename(columns={"cultivo_dominante": "cultivo_original"})
        nueva = _cultivo_dominante_por_superficie(
            datos_ciclo, columna_nueva
        ).rename(columns={"cultivo_dominante": "cultivo_nuevo"})
        comparacion = original[["cvegeo", "cultivo_original"]].merge(
            nueva[["cvegeo", "cultivo_nuevo"]],
            on="cvegeo", how="outer", validate="one_to_one",
        )
        comparacion["Nomcicloproductivo"] = ciclo
        comparacion["cambio_dominante"] = (
            comparacion["cultivo_original"].notna()
            & comparacion["cultivo_nuevo"].notna()
            & comparacion["cultivo_original"].ne(comparacion["cultivo_nuevo"])
        )
        comparaciones.append(comparacion)
        mapa = geometrias.merge(
            comparacion, on="cvegeo", how="left", validate="one_to_one"
        )
        for fila, (campo, etiqueta) in enumerate((
            ("cultivo_original", "Original 2025"),
            ("cultivo_nuevo", f"Escenario {escenario}"),
        )):
            colores = mapa[campo].map(paleta).fillna("#eeeeee")
            mapa.plot(
                ax=ejes[fila, columna], color=colores,
                edgecolor="white", linewidth=0.04,
            )
            ejes[fila, columna].set_axis_off()
            cambios = int(comparacion["cambio_dominante"].sum())
            subtitulo = f"{etiqueta} · {cambios:,} cambios" if fila else etiqueta
            ejes[fila, columna].set_title(
                f"{ciclo}\n{subtitulo}", fontsize=13
            )

    leyenda = [Patch(facecolor=paleta[c], label=c) for c in cultivos]
    leyenda.append(Patch(facecolor="#eeeeee", label="Sin superficie elegible"))
    fig.suptitle(
        "Cultivo dominante antes y después de la redistribución por ciclo",
        fontsize=18,
    )
    fig.legend(
        handles=leyenda, title="Cultivo dominante", loc="lower center",
        bbox_to_anchor=(0.5, -0.01), ncol=5, frameon=False, fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.13, 1, 0.95))
    if ruta_salida is not None:
        ruta_salida = Path(ruta_salida)
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(ruta_salida, dpi=dpi, bbox_inches="tight")
    return fig, ejes, pd.concat(comparaciones, ignore_index=True)


def crear_series_productivas_principales(
    agricultura: pd.DataFrame,
    top_n: int = 6,
    unidad: str = "Tonelada",
    ruta_salida: str | Path | None = None,
):
    """Grafica superficie, produccion y rendimiento de cultivos principales."""
    requeridas = {
        "Anio", "Nomcultivo", "Nomunidad", "Cosechada", "Volumenproduccion",
    }
    faltantes = requeridas - set(agricultura.columns)
    if faltantes:
        raise KeyError(f"Faltan columnas productivas: {sorted(faltantes)}")
    datos = agricultura.loc[agricultura["Nomunidad"].eq(unidad), list(requeridas)].copy()
    for columna in ["Cosechada", "Volumenproduccion"]:
        datos[columna] = pd.to_numeric(datos[columna], errors="coerce").fillna(0)
    cultivos = (
        datos.groupby("Nomcultivo", observed=True)["Cosechada"]
        .sum().nlargest(top_n).index.tolist()
    )
    serie = (
        datos.loc[datos["Nomcultivo"].isin(cultivos)]
        .groupby(["Anio", "Nomcultivo"], as_index=False, observed=True)
        .agg(Cosechada=("Cosechada", "sum"), Volumenproduccion=("Volumenproduccion", "sum"))
    )
    serie["Rendimiento"] = serie["Volumenproduccion"] / serie["Cosechada"]
    paleta = _paleta_cultivos(cultivos)
    fig, ejes = plt.subplots(3, 1, figsize=(14, 13), sharex=True)
    configuraciones = [
        ("Cosechada", "Superficie cosechada", "hectareas"),
        ("Volumenproduccion", "Volumen de produccion", "toneladas"),
        ("Rendimiento", "Rendimiento ponderado", "toneladas por hectarea"),
    ]
    for eje, (columna, titulo, unidad_eje) in zip(ejes, configuraciones):
        for cultivo in cultivos:
            bloque = serie.loc[serie["Nomcultivo"].eq(cultivo)]
            eje.plot(bloque["Anio"], bloque[columna], color=paleta[cultivo], linewidth=2, label=cultivo)
        eje.set_title(titulo, loc="left", fontsize=13)
        eje.set_ylabel(unidad_eje)
        eje.grid(alpha=0.2)
    ejes[-1].set_xlabel("Año")
    fig.legend(loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0))
    fig.suptitle("Trayectoria de los principales cultivos medidos en toneladas", fontsize=17)
    fig.tight_layout(rect=(0, 0.06, 1, 0.96))
    if ruta_salida is not None:
        ruta_salida = Path(ruta_salida); ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(ruta_salida, dpi=170, bbox_inches="tight")
    return fig, ejes, serie


def crear_mapa_estabilidad_rendimiento(
    agricultura: pd.DataFrame,
    municipios: gpd.GeoDataFrame,
    cultivo: str = "Maíz grano",
    unidad: str = "Tonelada",
    minimo_anios: int = 10,
    ruta_salida: str | Path | None = None,
):
    """Mapea el coeficiente de variacion anual del rendimiento municipal."""
    tiene_historial = {
        "rendimiento_hist_anios", "rendimiento_hist_media",
        "rendimiento_hist_desviacion", "rendimiento_hist_cv",
    }.issubset(agricultura.columns)
    if tiene_historial:
        columnas = [
            "cvegeo", "Anio", "Nomcicloproductivo", "Nommodalidad",
            "rendimiento_hist_anios", "rendimiento_hist_media",
            "rendimiento_hist_desviacion", "rendimiento_hist_cv",
        ]
        datos = agricultura.loc[
            agricultura["Nomcultivo"].eq(cultivo)
            & agricultura["Nomunidad"].eq(unidad), columnas,
        ].copy()
        datos["cvegeo"] = datos["cvegeo"].astype("string").str.zfill(5)
        datos = (
            datos.sort_values("Anio")
            .drop_duplicates(
                ["cvegeo", "Nomcicloproductivo", "Nommodalidad"], keep="last"
            )
        )
        estabilidad = datos.groupby("cvegeo", as_index=False, observed=True).agg(
            anios=("rendimiento_hist_anios", "max"),
            rendimiento_medio=("rendimiento_hist_media", "median"),
            rendimiento_desviacion=("rendimiento_hist_desviacion", "median"),
            coeficiente_variacion=("rendimiento_hist_cv", "median"),
        )
        estabilidad = estabilidad.loc[
            estabilidad["anios"].ge(minimo_anios)
            & estabilidad["coeficiente_variacion"].notna()
        ].copy()
    else:
        datos = agricultura.loc[
            agricultura["Nomcultivo"].eq(cultivo)
            & agricultura["Nomunidad"].eq(unidad),
            ["cvegeo", "Anio", "Cosechada", "Volumenproduccion"],
        ].copy()
        datos["cvegeo"] = datos["cvegeo"].astype("string").str.zfill(5)
        datos[["Cosechada", "Volumenproduccion"]] = datos[["Cosechada", "Volumenproduccion"]].apply(pd.to_numeric, errors="coerce")
        anual = datos.groupby(["cvegeo", "Anio"], as_index=False).agg(
            Cosechada=("Cosechada", "sum"), Volumenproduccion=("Volumenproduccion", "sum")
        )
        anual = anual.loc[anual["Cosechada"].gt(0)]
        anual["Rendimiento"] = anual["Volumenproduccion"] / anual["Cosechada"]
        estabilidad = anual.groupby("cvegeo", as_index=False).agg(
            anios=("Anio", "nunique"), rendimiento_medio=("Rendimiento", "mean"),
            rendimiento_desviacion=("Rendimiento", "std"),
        )
        estabilidad = estabilidad.loc[estabilidad["anios"].ge(minimo_anios)].copy()
        estabilidad["coeficiente_variacion"] = estabilidad["rendimiento_desviacion"] / estabilidad["rendimiento_medio"]
    mapa = preparar_geometrias_municipales(municipios).merge(estabilidad, on="cvegeo", how="left", validate="one_to_one")
    limite = estabilidad["coeficiente_variacion"].quantile(0.95)
    fig, ax = plt.subplots(figsize=(13, 9))
    mapa.plot(
        ax=ax, column="coeficiente_variacion", cmap="RdYlGn_r", vmin=0, vmax=limite,
        legend=True, missing_kwds={"color": "#eeeeee", "label": "Historia insuficiente"},
        edgecolor="white", linewidth=0.04,
        legend_kwds={"label": "Coeficiente de variacion (menor = mas estable)", "shrink": 0.7},
    )
    ax.set_axis_off(); ax.set_title(f"Estabilidad municipal del rendimiento · {cultivo}\nMinimo {minimo_anios} años", fontsize=16)
    fig.tight_layout()
    if ruta_salida is not None:
        ruta_salida = Path(ruta_salida); ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(ruta_salida, dpi=170, bbox_inches="tight")
    return fig, ax, mapa


def crear_siniestros_anomalias_clima(
    agricultura: pd.DataFrame,
    ruta_salida: str | Path | None = None,
):
    """Relaciona siniestros nacionales con desviaciones climáticas locales.

    La precipitación se expresa como cambio porcentual respecto al promedio
    histórico de cada municipio (y ciclo, cuando se usa clima por ciclo). Así
    no se promedian directamente milímetros de regiones con escalas de lluvia
    muy distintas. La temperatura conserva la diferencia en grados Celsius.
    """
    meses = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    temp = [f"temperatura_{mes}_c" for mes in meses]
    lluvia = [f"precipitacion_{mes}_mm" for mes in meses]
    basicas = {"cvegeo", "Anio", "Siniestrada"}
    faltantes_basicas = basicas - set(agricultura.columns)
    if faltantes_basicas:
        raise KeyError(f"Faltan columnas para anomalias: {sorted(faltantes_basicas)}")

    if set(temp + lluvia).issubset(agricultura.columns):
        clima = agricultura[["cvegeo", "Anio", *temp, *lluvia]].drop_duplicates(
            ["cvegeo", "Anio"]
        ).copy()
        clima[temp + lluvia] = clima[temp + lluvia].apply(
            pd.to_numeric, errors="coerce"
        )
        clima["temperatura_referencia_c"] = clima[temp].mean(axis=1)
        clima["precipitacion_referencia_mm"] = clima[lluvia].sum(
            axis=1, min_count=10
        )
        grupos_clima = ["cvegeo"]
    else:
        columnas_ciclo = {
            "Nomcicloproductivo", "temperatura_media_ciclo_c",
            "precipitacion_ciclo_mm",
        }
        faltantes_ciclo = columnas_ciclo - set(agricultura.columns)
        if faltantes_ciclo:
            raise KeyError(
                "Se requieren columnas mensuales o clima por ciclo; faltan: "
                f"{sorted(faltantes_ciclo)}"
            )
        clima = agricultura[[
            "cvegeo", "Anio", "Nomcicloproductivo",
            "temperatura_media_ciclo_c", "precipitacion_ciclo_mm",
        ]].drop_duplicates(
            ["cvegeo", "Anio", "Nomcicloproductivo"]
        ).copy()
        clima["temperatura_referencia_c"] = pd.to_numeric(
            clima["temperatura_media_ciclo_c"], errors="coerce"
        )
        clima["precipitacion_referencia_mm"] = pd.to_numeric(
            clima["precipitacion_ciclo_mm"], errors="coerce"
        )
        grupos_clima = ["cvegeo", "Nomcicloproductivo"]

    grupos = clima.groupby(grupos_clima, observed=True)
    temperatura_base = grupos["temperatura_referencia_c"].transform("mean")
    precipitacion_base = grupos["precipitacion_referencia_mm"].transform("mean")
    clima["anomalia_temperatura_c"] = (
        clima["temperatura_referencia_c"] - temperatura_base
    )
    clima["anomalia_precipitacion_pct"] = (
        100
        * (clima["precipitacion_referencia_mm"] - precipitacion_base)
        / precipitacion_base.where(precipitacion_base.gt(0))
    )
    clima_anual = clima.groupby("Anio", as_index=False).agg(
        anomalia_temperatura_c=("anomalia_temperatura_c", "mean"),
        anomalia_precipitacion_pct=("anomalia_precipitacion_pct", "mean"),
    )
    siniestros = agricultura.assign(
        Siniestrada=pd.to_numeric(agricultura["Siniestrada"], errors="coerce")
    ).groupby("Anio", as_index=False)["Siniestrada"].sum()
    resumen = clima_anual.merge(siniestros, on="Anio", validate="one_to_one")
    resumen["superficie_siniestrada_millones_ha"] = resumen["Siniestrada"] / 1e6
    fig, ejes = plt.subplots(1, 2, figsize=(14, 5.8))
    for eje, columna, etiqueta, titulo, color in (
        (
            ejes[0], "anomalia_precipitacion_pct",
            "Desviación media de precipitación respecto al promedio local (%)",
            "Años más secos ← 0 → Años más lluviosos", "#3c78a8",
        ),
        (
            ejes[1], "anomalia_temperatura_c",
            "Desviación media de temperatura respecto al promedio local (°C)",
            "Años más fríos ← 0 → Años más cálidos", "#d46a4c",
        ),
    ):
        rho = resumen[columna].rank().corr(resumen["Siniestrada"].rank())
        eje.scatter(
            resumen[columna], resumen["superficie_siniestrada_millones_ha"],
            s=58, color=color, alpha=0.82, edgecolor="white", linewidth=0.5,
        )
        eje.axvline(0, color="#5d6863", linewidth=1.1, linestyle="--", alpha=0.8)
        for _, fila in resumen.nlargest(3, "Siniestrada").iterrows():
            eje.annotate(
                int(fila["Anio"]),
                (fila[columna], fila["superficie_siniestrada_millones_ha"]),
                xytext=(5, 5), textcoords="offset points", fontsize=8,
            )
        eje.text(
            0.03, 0.96, f"ρ Spearman = {rho:.2f}", transform=eje.transAxes,
            va="top", fontsize=9, color="#35443e",
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8},
        )
        eje.set_title(titulo, fontsize=11)
        eje.set_xlabel(etiqueta)
        eje.set_ylabel("Superficie siniestrada (millones de ha)")
        eje.grid(alpha=0.2)
    fig.suptitle(
        "Superficie siniestrada y desviaciones climáticas nacionales",
        fontsize=16,
    )
    fig.text(
        0.5, 0.015,
        "Cada punto representa un año. Las desviaciones se calculan primero "
        "contra el promedio 2003–2025 de cada municipio/ciclo y luego se "
        "promedian nacionalmente. Asociación no implica causalidad.",
        ha="center", fontsize=9, color="#4f5d57",
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.94))
    if ruta_salida is not None:
        ruta_salida = Path(ruta_salida); ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(ruta_salida, dpi=170, bbox_inches="tight")
    return fig, ejes, resumen


def crear_cobertura_anual_datos(
    agricultura: pd.DataFrame,
    ruta_salida: str | Path | None = None,
):
    """Grafica cambios anuales en registros, municipios y cultivos."""
    resumen = agricultura.groupby("Anio", as_index=False).agg(
        registros=("cvegeo", "size"), municipios=("cvegeo", "nunique"),
        cultivos=("Nomcultivo", "nunique"),
    )
    fig, ejes = plt.subplots(3, 1, figsize=(13, 10), sharex=True)
    for eje, columna, titulo, color in (
        (ejes[0], "registros", "Registros", "#285947"),
        (ejes[1], "municipios", "Municipios", "#d98d69"),
        (ejes[2], "cultivos", "Cultivos distintos", "#3c78a8"),
    ):
        eje.plot(resumen["Anio"], resumen[columna], marker="o", color=color, linewidth=2)
        eje.axvspan(2019.5, 2021.5, color="#f4c453", alpha=0.25)
        eje.set_ylabel(titulo); eje.grid(alpha=0.2)
    ejes[-1].set_xlabel("Año")
    fig.suptitle("Cobertura anual del dataset · 2020–2021 requieren cautela", fontsize=16)
    fig.tight_layout()
    if ruta_salida is not None:
        ruta_salida = Path(ruta_salida); ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(ruta_salida, dpi=170, bbox_inches="tight")
    return fig, ejes, resumen


def crear_selector_mapa_estabilidad(
    agricultura: pd.DataFrame,
    municipios: gpd.GeoDataFrame,
    unidad: str = "Tonelada",
    minimo_anios: int = 10,
):
    """Crea un selector Jupyter para explorar estabilidad por cultivo."""
    try:
        import ipywidgets as widgets
        from IPython.display import display
    except ImportError as error:
        raise ImportError(
            "El selector requiere ipywidgets. Ejecuta `uv sync` y reinicia el kernel."
        ) from error

    requeridas = {
        "Nomcultivo", "Nomunidad", "rendimiento_hist_anios",
        "rendimiento_hist_cv",
    }
    faltantes = requeridas - set(agricultura.columns)
    if faltantes:
        raise KeyError(
            "El selector requiere el dataset histórico; faltan: "
            f"{sorted(faltantes)}"
        )
    elegibles = agricultura.loc[
        agricultura["Nomunidad"].eq(unidad)
        & agricultura["rendimiento_hist_anios"].ge(minimo_anios)
        & agricultura["rendimiento_hist_cv"].notna()
    ]
    cobertura = (
        elegibles.groupby("Nomcultivo", observed=True)["cvegeo"]
        .nunique().sort_values(ascending=False)
    )
    if cobertura.empty:
        raise ValueError("No hay cultivos con historial suficiente para el selector.")
    opciones = [
        (f"{cultivo} · {municipios_n:,} municipios", cultivo)
        for cultivo, municipios_n in cobertura.items()
    ]
    selector = widgets.Dropdown(
        options=opciones,
        value=opciones[0][1],
        description="Cultivo:",
        layout=widgets.Layout(width="520px"),
        style={"description_width": "70px"},
    )
    salida = widgets.Output()

    def actualizar(*_):
        with salida:
            salida.clear_output(wait=True)
            figura, _, mapa = crear_mapa_estabilidad_rendimiento(
                agricultura,
                municipios,
                cultivo=selector.value,
                unidad=unidad,
                minimo_anios=minimo_anios,
                ruta_salida=None,
            )
            display(figura)
            plt.close(figura)
            disponibles = int(mapa["coeficiente_variacion"].notna().sum())
            print(
                f"{selector.value}: {disponibles:,} municipios con "
                f"al menos {minimo_anios} años de historial."
            )

    selector.observe(actualizar, names="value")
    actualizar()
    return widgets.VBox([
        widgets.HTML(
            "<b>Estabilidad histórica municipal</b><br>"
            "Verde = menor variabilidad; rojo = mayor variabilidad."
        ),
        selector,
        salida,
    ])

