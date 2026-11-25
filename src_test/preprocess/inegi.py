from config.paths import datapaths
from config.links import INEGI_MEXICO_REF, EDAF_API, USOV_API
from zipfile import ZipFile
import os


# Mapa de México
mexico_map = INEGI_MEXICO_REF.split("/")[-1]
mexico_folder = mexico_map.split(".")[0]
if not (datapaths['raw']['INEGI'] / mexico_folder).exists():
    with ZipFile(datapaths['pure']['INEGI'] / mexico_map) as mexico:
        mexico.extractall(datapaths['raw']['INEGI'] / mexico_folder)


# Mapas de Edafologia
edaf_filenames = [f.split("/")[-1] for f in EDAF_API]

for file in edaf_filenames:
    if not (datapaths['raw']['INEGI'] / file.replace(".zip", "")).exists():
        print("Extrayendo ", file)
        with ZipFile(datapaths['pure']['INEGI'] / file, "r") as edaf_zip:
            edaf_zip.extractall(datapaths['raw']['INEGI'] / file.replace(".zip", ""))





# Mapas de Zonas Agricolas.
# Extracción
usov_filenames = [f.split("/")[-1] for f in USOV_API]

for file in usov_filenames:
    if not (datapaths['raw']['INEGI'] / file.replace(".zip", "")).exists():
        print("Extrayendo ", file)
        with ZipFile(datapaths['pure']['INEGI'] / file, "r") as edaf_zip:
            edaf_zip.extractall(datapaths['raw']['INEGI'] / file.replace(".zip", ""))

# Selección de Información relevante

shps_usov = []
for usov in usov_filenames:
    folder = datapaths['raw']['INEGI'] / usov.replace(".zip", "")
    # Solo archivos .shp en subcarpetas
    shps_usov += list(folder.rglob("*.shp"))

principal_shps = [shp for shp in shps_usov if str(shp).split("/")[-1].endswith("g.shp") or str(shp).split("/")[-1].endswith("union.shp")]
complement_shps = [shp for shp in shps_usov if str(shp).split("/")[-1].endswith("c.shp")]

