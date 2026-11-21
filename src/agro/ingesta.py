# Ingesta de Datos

# DGSIAP: La Historia
from datasets.agricultura import descargar_datos_agricolas, descargar_diccionario_agricola
from proyecto_agronomia.config import ANIOS, AGRICULTURA_RAW_DIR
from datasets.inegi import obtener_municipios_inegi
from processing.integracion_climatica import puntos_representativos_municipales


# Conjuntos de Datos
archivos_agricolas = descargar_datos_agricolas(
    ANIOS
)

print(
    f"Archivos disponibles: "
    f"{len(archivos_agricolas)}"
)

for anio in ANIOS:
    if not (AGRICULTURA_RAW_DIR / f"agricola_{anio}.csv").exists():
        print(f"Falta agricola_{anio}.csv")

# Diccionario de Datos

ruta_diccionario = descargar_diccionario_agricola()

print(
    f"Diccionario disponible en: "
    f"{ruta_diccionario}"
)

# NASA POWER: El Clima

## Parte 1. Los puntos de interés

gdf_municipios_inegi = obtener_municipios_inegi()
df_puntos_nasa = puntos_representativos_municipales(gdf_municipios_inegi)

df_municipios_nasa = (
    df_puntos_nasa[["cvegeo", "nomgeo", "latitud", "longitud"]]
    .rename(columns={
        "nomgeo": "Nommunicipio",
        "latitud": "Latitud",
        "longitud": "Longitud",
    })
    .sort_values("cvegeo")
    .reset_index(drop=True)
)
df_municipios_nasa["cvegeo"] = df_municipios_nasa["cvegeo"].astype("string").str.zfill(5)

assert df_municipios_nasa["cvegeo"].is_unique
assert df_municipios_nasa[["Latitud", "Longitud"]].notna().all().all()
print(f"Municipios preparados: {len(df_municipios_nasa):,}")

## Parte 2. La descarga.