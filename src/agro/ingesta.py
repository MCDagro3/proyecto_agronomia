# Ingesta de Datos

from proyecto_agronomia.config import AGRICULTURA_RAW_DIR, ANIOS, ANIO_FINAL, ANIO_INICIAL
from datasets.agricultura import descargar_datos_agricolas, descargar_diccionario_agricola
from processing.integracion_climatica import puntos_representativos_municipales
from datasets.inegi import obtener_municipios_inegi
from datasets.clima_nasa import descargar_clima_nasa_mensual_por_celdas
from datasets.edafologia import descargar_edafologia_inegi


if __name__ == "__main__":
    # DGSIAP: La Historia
    print("Descargando los Datos del DGSIAP")
    ## Conjuntos de Datos
    archivos_agricolas = descargar_datos_agricolas(ANIOS)
    print(" - Conjunto de Datos")
    print(f"Archivos disponibles: {len(archivos_agricolas)}")

    for anio in ANIOS:
        if not (AGRICULTURA_RAW_DIR / f"agricola_{anio}.csv").exists():
            print(f"Falta agricola_{anio}.csv")

    ## Diccionario de Datos
    print(" - Diccionario de Datos")
    ruta_diccionario = descargar_diccionario_agricola()

    print(f"Diccionario disponible en: {ruta_diccionario}")

    # NASA POWER: El Clima
    print("Descarga DGSIAP Completada. Empezamos con los datos climaticos de NASA POWER")
    ## Parte 1. Los puntos de interés
    print("Preliminar: Obtener los puntos de interés")
    gdf_municipios_inegi = obtener_municipios_inegi()
    df_puntos_nasa = puntos_representativos_municipales(gdf_municipios_inegi)

    df_municipios_nasa = (
        df_puntos_nasa[["cvegeo", "nomgeo", "latitud", "longitud"]]
        .rename(
            columns={
                "nomgeo": "Nommunicipio",
                "latitud": "Latitud",
                "longitud": "Longitud",
            }
        )
        .sort_values("cvegeo")
        .reset_index(drop=True)
    )
    df_municipios_nasa["cvegeo"] = df_municipios_nasa["cvegeo"].astype("string").str.zfill(5)

    assert df_municipios_nasa["cvegeo"].is_unique
    assert df_municipios_nasa[["Latitud", "Longitud"]].notna().all().all()
    print(f"Municipios preparados: {len(df_municipios_nasa):,}")

    ## Parte 2. La descarga.
    print("Descargar la información climatica en los puntos seleccionados")
    EJECUTAR_AGREGACION_MENSUAL = True

    if EJECUTAR_AGREGACION_MENSUAL:
        df_clima_mensual = descargar_clima_nasa_mensual_por_celdas(
            municipios=df_municipios_nasa,
            inicio=ANIO_INICIAL,
            fin=ANIO_FINAL,
        )
        print(f"Registros generados: {len(df_clima_mensual):,}")
    else:
        print("Descarga omitida; se utilizará el CSV existente.")


    # INEGI Edafología.
    print("Información de NASA POWER Descargada. Concluimos con los datos del suelo.")
    ruta_edafologia = descargar_edafologia_inegi()

    print(
        f"Directorio de datos edafológicos: "
        f"{ruta_edafologia}"
    )