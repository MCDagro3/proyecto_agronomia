"""Construccion de activos compactos para el storytelling web."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import median

PROJ_ROOT = Path(__file__).resolve().parents[1]
RUTA_HISTORIAL = PROJ_ROOT / "data" / "processed" / "agricultura_clima_edafologia_historial_2003_2025.csv"
RUTA_COORDENADAS = PROJ_ROOT / "data" / "interim" / "inegi" / "municipios_coordenadas_inegi.csv"
RUTA_ESTADOS = PROJ_ROOT / "data" / "interim" / "inegi" / "estados_mexico_inegi.geojson"
RUTA_SALIDA = PROJ_ROOT / "reports" / "storytelling" / "estabilidad_data.js"


def _distancia_segmento(punto, inicio, fin):
    """Distancia euclidiana de un punto a un segmento en grados."""
    x, y = punto
    x1, y1 = inicio
    x2, y2 = fin
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    px, py = x1 + t * dx, y1 + t * dy
    return ((x - px) ** 2 + (y - py) ** 2) ** 0.5


def _simplificar_linea(puntos, tolerancia=0.025):
    """Simplifica una linea con Douglas-Peucker para el SVG web."""
    if len(puntos) <= 3:
        return puntos
    inicio, fin = puntos[0], puntos[-1]
    distancias = [_distancia_segmento(punto, inicio, fin) for punto in puntos[1:-1]]
    distancia_maxima = max(distancias, default=0)
    if distancia_maxima <= tolerancia:
        return [inicio, fin]
    indice = distancias.index(distancia_maxima) + 1
    izquierda = _simplificar_linea(puntos[: indice + 1], tolerancia)
    derecha = _simplificar_linea(puntos[indice:], tolerancia)
    return izquierda[:-1] + derecha


def _cargar_limites_estatales(ruta_estados):
    """Devuelve anillos estatales simplificados en longitud y latitud."""
    geojson = json.loads(Path(ruta_estados).read_text(encoding="utf-8"))
    anillos = []
    for feature in geojson["features"]:
        geometria = feature.get("geometry") or {}
        coordenadas = geometria.get("coordinates", [])
        if geometria.get("type") == "Polygon":
            poligonos = [coordenadas]
        elif geometria.get("type") == "MultiPolygon":
            poligonos = coordenadas
        else:
            continue
        for poligono in poligonos:
            if not poligono:
                continue
            exterior = poligono[0]
            # Omite islotes minusculos que no aportan legibilidad a esta escala.
            if len(exterior) < 4:
                continue
            simplificado = _simplificar_linea(exterior)
            if len(simplificado) >= 3:
                anillos.append([[round(x, 4), round(y, 4)] for x, y in simplificado])
    return anillos


def exportar_estabilidad_storytelling(
    ruta_historial: Path = RUTA_HISTORIAL,
    ruta_coordenadas: Path = RUTA_COORDENADAS,
    ruta_estados: Path = RUTA_ESTADOS,
    ruta_salida: Path = RUTA_SALIDA,
    unidad: str = "Tonelada",
    minimo_anios: int = 10,
) -> Path:
    """Exporta presencia y estabilidad municipal a JavaScript sin dependencias."""
    coordenadas = {}
    with Path(ruta_coordenadas).open(encoding="utf-8-sig", newline="") as archivo:
        for fila in csv.DictReader(archivo):
            coordenadas[fila["cvegeo"].zfill(5)] = (
                round(float(fila["Longitud"]), 5),
                round(float(fila["Latitud"]), 5),
                fila["Nommunicipio"],
            )

    ultimos = {}
    columnas = {
        "cvegeo", "Anio", "Nomcultivo", "Nomunidad", "Nomestado",
        "Nomcicloproductivo", "Nommodalidad", "rendimiento_hist_anios",
        "rendimiento_hist_media", "rendimiento_hist_cv",
    }
    with Path(ruta_historial).open(encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        faltantes = columnas - set(lector.fieldnames or [])
        if faltantes:
            raise KeyError(f"Faltan columnas para el storytelling: {sorted(faltantes)}")
        for fila in lector:
            if fila["Nomunidad"] != unidad or not fila["rendimiento_hist_cv"]:
                continue
            try:
                anios = int(float(fila["rendimiento_hist_anios"]))
                anio = int(fila["Anio"])
                cv = float(fila["rendimiento_hist_cv"])
                rendimiento = float(fila["rendimiento_hist_media"])
            except (TypeError, ValueError):
                continue
            cvegeo = fila["cvegeo"].zfill(5)
            if anios < minimo_anios or cvegeo not in coordenadas:
                continue
            clave = (fila["Nomcultivo"], cvegeo, fila["Nomcicloproductivo"], fila["Nommodalidad"])
            anterior = ultimos.get(clave)
            if anterior is None or anio > anterior[0]:
                ultimos[clave] = (anio, cv, rendimiento, anios, fila["Nomestado"])

    municipal = {}
    for (cultivo, cvegeo, _, _), (_, cv, rendimiento, anios, estado) in ultimos.items():
        grupo = municipal.setdefault(
            (cultivo, cvegeo), {"cv": [], "rendimiento": [], "anios": [], "estado": estado}
        )
        grupo["cv"].append(cv)
        grupo["rendimiento"].append(rendimiento)
        grupo["anios"].append(anios)

    cultivos = {}
    for (cultivo, cvegeo), valores in municipal.items():
        longitud, latitud, municipio = coordenadas[cvegeo]
        cultivos.setdefault(cultivo, []).append([
            longitud, latitud, round(median(valores["cv"]), 4),
            int(max(valores["anios"])), round(median(valores["rendimiento"]), 3),
            municipio, valores["estado"],
        ])
    cultivos = dict(sorted(cultivos.items(), key=lambda item: (-len(item[1]), item[0])))
    contenido = {
        "minimo_anios": minimo_anios,
        "limites_estatales": _cargar_limites_estatales(ruta_estados),
        "cultivos": cultivos,
    }
    ruta_salida = Path(ruta_salida)
    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    ruta_salida.write_text(
        "window.ESTABILIDAD_CULTIVOS = "
        + json.dumps(contenido, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    return ruta_salida


if __name__ == "__main__":
    print(exportar_estabilidad_storytelling())
