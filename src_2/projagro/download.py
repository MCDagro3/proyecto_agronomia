# Descarga de los datos
from config.parameters import DGSIAP_CATEGORY
from datasources.dgsiap import scraper
from datasources.mapbiomas import descargar_mapbiomas
from config.links import EDAF_API, INEGI_MEXICO_REF, USOV_API
from config.preloads import GALLERY
from config.tools import download_file
from config.paths import datapaths
from datasources.inegi import download_inegi
import json


def download_dgsiap(categories = DGSIAP_CATEGORY, **kwargs):
    path_tree = kwargs.get("tree", GALLERY['DGSIAP']['tree'])
    if not path_tree.exists():
        path_data = kwargs.get("data", GALLERY['DGSIAP']['data'])
        if not path_data.exists():
            scraper(categories,path_data=path_data)
        with open(path_data, "r") as dgsiap:
            dg_tree = json.load(dgsiap)
        dgsiap_tree = {}
        for category in dg_tree.keys():
            tree = dg_tree[category]
            cat_tree = { "codebook": "", "datasets": {} }
            for file in tree.values():
                for k in file.keys():
                    print(k)
                    if k == "info":
                        url = file[k]['download']
                        cat_tree['codebook'] = download_file(url, datapaths['pure']['DGSIAP'])
                    if k in tree['datasets'].keys():
                        url = tree['datasets'][k]
                        cat_tree['datasets'][k] = download_file(url, datapaths['pure']['DGSIAP'])
            dgsiap_tree[category] = cat_tree
        path_tree.write_text(json.dumps(dgsiap_tree, ensure_ascii=False, indent=4), encoding="utf-8")
        print(f"Los archivos fueron descargados en {datapaths['pure']['DGSIAP']}")
        print(f"Las ubicaciones de los archivos estan en {path_tree}")
    else:
        print(f"Los archivos ya estan descargados en {path_tree}")


# Descarga Mapa de México
download_inegi(INEGI_MEXICO_REF)


# Descarga de Mapas de Edafologia
for edaf in EDAF_API:
    download_inegi(edaf)


# Descarga de Mapas de Carta de Uso de Suelo
for usov in USOV_API:
    print("Descargando ", usov)
    download_inegi(usov)

# Descarga de Mapbiomas
descargar_mapbiomas()