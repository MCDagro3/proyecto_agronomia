# Conjunto de archivos para acortar procesamiento.
from config.paths import datapaths

GALLERY = {
    "DGSIAP":{
        "data" : datapaths['preload']['DGSIAP'] / "prodagro_routes.json",
        "meta" : datapaths['preload']['DGSIAP'] / "prodagro_meta.json",
        "tree": datapaths['preload']['DGSIAP'] / "prodagro_files.json"
    }
}

