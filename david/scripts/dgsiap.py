"""
    Gestor de la información obtenida del DGSIAP
"""

from scripts.config import source_links, dgsiap_info
from bs4 import BeautifulSoup
import yarl
import re
import requests as r


"""
    Fase Uno: El Diccionario Maestro
"""
# Conexión con la fuente de información
dgsiap_link = source_links['DGSIAP']['request'] / dgsiap_info
response = r.get(dgsiap_link)
response.raise_for_status()


# Definimos nuestra zona de trabajo.
dgsiap = BeautifulSoup(response.content, "lxml")
dg_main = dgsiap.find("main")
dg_secs = dg_main.find_all("section", recursive=False)




def blocks_intro(sections):
    history = sections[3]
    data_title = history.find("div", {"class":"mb-0 h5 font-weight-bold section-title"}).text
    data_content = history.find("div", {"id":"dataAccordion"})
    blocks = data_content.find_all("div", recursive=False)
    data_blocks = {b.find("div", {"class":"d-flex align-items-center"}).text.strip(): b for b in blocks}
    # print(f"Los datos historicos se presentan en el espacio denominado: {data_title}")
    data_blocks_f = [f"{k + 1}. {b}" for k, b in enumerate(data_blocks.keys())]
    # print(f"Los datos se encuentran divididos en 3 bloques:\n\n{"\n".join(data_blocks_f)}")
    return data_blocks


def format_codebook(category):
    data_blocks = blocks_intro(dg_secs)
    assert category in list(data_blocks.keys()), "Revisa la categoria"
    if category == "Municipal":
        raw = dg_secs[2]
        sec = raw.find("div", {"class":"dict-section"})
    else:
        sec = data_blocks[category]
    mini_blocks = sec.find_all("div", {"class":re.compile(r"col-12 col-md-6*?")})
    codebook, metadata = mini_blocks[0], mini_blocks[1]
    codebook_info = {"title": codebook.find("h2").text, 
                     "description": codebook.find("p").text,
                     "download": codebook.find("a")['href']}
    meta = metadata.find("div")
    datetype = meta.find_all("div", recursive=False)
    metadata_info = {"title": meta.find("h4").text,
                     "state": datetype[0].find("span", {"class":"label"}).text,
                     "lastdate": datetype[0].find("span", {"class":"value"}).text,
                     "range": datetype[1].find("span", {"class":"label"}).text,
                     "size": datetype[1].find("span", {"class":"value"}).text
                    }
    return metadata_info, codebook_info


def dict_master(sections=dg_secs):
    data_blocks=blocks_intro(sections)

    # Diccionario de Datos
    data_dicts = {db:{} for db in data_blocks.keys()}

    for db in data_dicts.keys():
        data_dicts[db]["metadata"], data_dicts[db]["info"] = format_codebook(db)

    data_history = {db:[] for db in data_blocks.keys()}

    for db in data_history.keys():
        block = data_blocks[db]
        con_data = block.find_all("a", {"class":"dl-btn"})
        href_data = [yarl.URL(a['href']) for a in con_data]
        data_history[db] += href_data


    # Conglomerado en un solo dicctionario. 
    assert set(data_history.keys()) == set(data_dicts.keys()), "Revise los bloques utilizados"
    connector = {b: {"Metadata": data_dicts[b],
                  "Datasets": data_history[b]}
                   for b in data_dicts.keys()}
    return connector
