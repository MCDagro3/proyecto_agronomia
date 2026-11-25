# Descarga de los datoss del DGSIAP
from config.preloads import GALLERY
from config.links import DGSIAP_REF
from config.tools import require_tag
from bs4 import BeautifulSoup
import json
import re
import requests


# Obtención del url para la descarga de los archivos.
dgsiap_elements = DGSIAP_REF.split("/")
dgsiap_api = f"{dgsiap_elements[0]}//{dgsiap_elements[2]}"


# Ruta para guardar las rutas previamente recopiladas.
preload_agro = GALLERY['DGSIAP']['data']
preload_meta = GALLERY['DGSIAP']['meta']


def locate_category_content(category, last_update, data_blocks):
    """
        Dada una de las categorias disponibles en el DGSIAP. Recupera su ubicación
    """
    categories = list(data_blocks.keys())
    assert category in categories, "Revisa la categoria"
    if category == last_update['name']:
        raw = last_update['section']
        sec = raw.find("div", {"class":"dict-section"})
    else:
        sec = data_blocks[category]
    return sec

def dgsiap_codebook(category, last_update, data_blocks):
    """
        Se extraen los datos principales a los diccionarios de datos.
            * Descripción.
            * Metadatos.
            * Enlace de Descarga.
    """
    sec = locate_category_content(category, last_update, data_blocks)
    mini_blocks = sec.find_all("div", {"class":re.compile(r"col-12 col-md-6*?")})
    codebook, metadata = mini_blocks[0], mini_blocks[1]
    codebook_info = {"title": require_tag(codebook.find("h2"), "h2").text, 
                     "description": require_tag(codebook.find("p"), "p").text,
                     "download": f"{dgsiap_api}{require_tag(codebook.find("a"), "a")['href']}"}
    
    meta = require_tag(metadata.find("div"), "div")
    datetype = meta.find_all("div", recursive=False)
    metadata_info = {"title": require_tag(meta.find("h4"), "h4").text,
                     "state": [s.text for s in datetype[0].find_all("span")],
                     "range": [s.text for s in datetype[1].find_all("span")]}
    return metadata_info, codebook_info

def dgsiap_datasets(category, data_blocks: dict):
    categories = list(data_blocks.keys())
    assert category in categories, "Revisa la categoria"
    sec = data_blocks[category]
    dwld_pars = sec.find_all("a", {"class":"dl-btn"})
    datapars = {}
    for hpars in dwld_pars:
        pars = hpars['href']
        if not isinstance(pars, str):
            raise RuntimeError("Se esperaba un href string en DGSIAP")
        year = f"{pars.split("=")[-1]}"
        datapars[year] = f"{dgsiap_api}{pars}"
    return datapars


def dictmaster(category, last_update, data_blocks):
    """
        Entrega los metadatos y conjuntos de datos de la categoria a tu eleccion.
    """
    datadict_meta, datadict_info  = dgsiap_codebook(category, last_update, data_blocks)
    datasets = dgsiap_datasets(category, data_blocks)
    dgsiap = {
        "codebook": {"meta": datadict_meta,
                     "info": datadict_info},
        "datasets": datasets
    }
    return dgsiap


def scraper(categories: str|list, **kwargs):
    """
        Realiza un WebSraping a la página del DGSIAP donde se obtienen
        * Datos (Instancias y Diccionarios)
        * Información General de la página (opcional)
    """
    path_data = kwargs.get("route", preload_agro)
    path_meta = kwargs.get("meta", preload_meta)


    # Resumen del WebScrapping de la página del DGSIAP
    print("Conexión con la pagina de referencia", DGSIAP_REF)
    response = requests.get(DGSIAP_REF)
    response.raise_for_status()
    print("Conexión Establecida. Código", response.status_code)

    # Definimos nuestra zona de trabajo.
    content = BeautifulSoup(response.content, "lxml")
    dgsiap_main = require_tag(content.find("main"), "<main>")
    dgsiap_secs = dgsiap_main.find_all("section", recursive=False)

    # Encabezado de la página.
    step1 = dgsiap_secs[1]
    description_page = []
    for d1 in step1.find_all("div", recursive=False):
        div_text = d1.text
        div_mn = div_text.replace("\n", "")
        div_mt = div_mn.replace("\t", "")
        description_page.append(div_mt)

    # Seccion Última publicación.
    step2 = dgsiap_secs[2]
    last_update = step2.find_all("div", recursive=False)
    last_title = last_update[0]
    last_title_name = require_tag(last_title.find("div", {"class": "section-title"}), "section-title")
    last_content = last_update[1]
    last_content_meta = last_content.find_all("div", {"class":"meta-row"})
    last_update_block = {"name":"Municipal", "section": step2}

    # Conjunto de Datos
    step3 = dgsiap_secs[3]
    step31 = require_tag(step3.find("div", {"id":"dataAccordion"}), "dataAccordion")
    step32 = step31.find_all("div", recursive=False)
    divcode = "d-flex align-items-center"
    data_blocks = {require_tag(b.find("div", {"class":divcode}), divcode).text.strip(): b for b in step32}
    total_categories = list(data_blocks.keys())
    dgsiap_routes = {}
    if not isinstance(categories, list):
        categories = [categories]
    for category in categories:
        assert category in total_categories, "Revisa las categorias de interés"
        dgsiap_routes[category] = dictmaster(category, last_update_block, data_blocks)
    print("Creando arbol de rutas de producción agrícola")
    path_data.write_text(json.dumps(dgsiap_routes, ensure_ascii=False, indent=4), encoding="utf-8")
    print(f"Las rutas estan en {path_data}")
    if path_meta.exists():
        print(f"La metadata del DGSIAP se encuentra en {path_meta}" )
    else:
        metadgsiap = {}
        print(f"Agregando metadata de {DGSIAP_REF}")
        step0 = dgsiap_secs[0]
        page_initial = [h.text for h in step0.find_all("a") if h.text != ""]
        metadgsiap["source"] = page_initial[0]
        metadgsiap["data_specs"] = page_initial[1]
        metadgsiap['data_title'] = description_page[1]
        metadgsiap['data_description'] = description_page[2]
        metadgsiap["principal_data"] = last_title_name.text.replace("\t", "").strip("\n")
        metadgsiap['principal_metadata'] = {
            "Estado": [s.text for s in last_content_meta[0].find_all("span")],
            "Cobertura": [s.text for s in last_content_meta[1].find_all("span")]}
        metadgsiap['data_blocks'] = list(data_blocks.keys())
        print(f"Generando archivo con metadata")
        path_meta.write_text(json.dumps(metadgsiap, ensure_ascii=False, indent=4), encoding="utf-8")
        print(f"La metadata esta en {path_meta}")
