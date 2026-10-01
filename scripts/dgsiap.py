"""
    Conexión al conjunto de datos abiertos DGSIAP y creación del diccionario maestro.
"""
# Importamos librerias requeridas
import requests
from bs4 import BeautifulSoup
import yarl
import re
from scripts.config import dgsiap_page



def introduction(**kwargs):
    menu = kwargs.get("menu", 0)

    if menu:
        ## Menu para elegir entre los datos agricolas y los datos pecuarios.
        print("Bienvenido al script de descarga de datos abiertos del DGSIAP.")

        info = {
            "Agricola": "Agricola.php",
            "Pecuaria": "Pecuario.php",
        }

        value = input(f"Ingrese la categoria de los datos a consultar.\n{" \n".join(info.keys())}: ")

        try:
            BOT_URL = dgsiap_page / info[value]
        except KeyError:
            print("Categoria no valida. Por favor, ingrese una categoria valida.")
            exit(1)
    else:
        value = "Agricola.php"
        BOT_URL = dgsiap_page / value

    # Intento de conexión
    response = requests.get(BOT_URL)
    if response.status_code != 200:
        print(f"Error al acceder a la pagina: {response.status_code}")
        exit(1)
    else:
        print("Conexion Establecida")

    # Mandamos la información para su recopilación
    page = BeautifulSoup(response.content, "lxml")

    # Definimos nuestra zona de trabajo.
    content = page.find("main")

    # Dividiremos la pagina en sus secciones principales
    sections = content.find_all("section", recursive=False)

    print(f"Usted escogio {value.split(".")[0]}")
    return sections


def welcome(sections):
    tree = sections[0]
    intro_data = []
    for t in tree.find_all("li"):
        if t.text!="":
            intro_data.append(t.text)

    print(f"De parte de la {intro_data[0]} te damos la bienvenida al conjunto de {intro_data[1]} de la {intro_data[2]}")


def basic_intro(sections):
    intro = sections[1]
    raw_intro=list()
    for t in intro.find_all("div", recursive=False):
        if t.text!="":
            raw_block=(t.text).split("\t")
            for raw in raw_block:
                if raw.strip() != "":
                    raw_intro.append(raw)

    print(f"Conjuntos de {raw_intro[0]} sobre {raw_intro[1]}")
    print(raw_intro[-1])


def blocks_intro(sections):
    history = sections[3]
    data_title = history.find("div", {"class":"mb-0 h5 font-weight-bold section-title"}).text
    data_content = history.find("div", {"id":"dataAccordion"})
    blocks = data_content.find_all("div", recursive=False)
    data_blocks = {b.find("div", {"class":"d-flex align-items-center"}).text.strip(): b for n, b in enumerate(blocks)}
    print(f"Los datos historicos se presentan en el espacio denomiado: {data_title}")
    data_blocks_f = [f"{k + 1}. {b}" for k, b in enumerate(data_blocks.keys())]
    print(f"Los datos se encuentran divididos en 3 bloques:\n\n{"\n".join(data_blocks_f)}")
    return data_blocks


def get_catalog(sections):
    sec = sections[2]
    block = sec.find("div", {"class":"dict-section"})
    mini_blocks = block.find_all("div", {"class":re.compile(r"col-12 col-md-6*?")})
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


def get_data(sections):
    sec = sections[2]
    block = sec.find("div", {"class":"bento-card h-100"})
    u = block.find_all("div", recursive=False)
    data_info = [s.text for s in u[0].find_all("span", recursive=False)]
    data_get = u[1]
    data_link = data_get.find("a")['href']
    return data_info, data_link


def dict_master():
    sections = introduction()
    data_blocks=blocks_intro(sections)
    last = sections[2]
    # search_title_section=last.find("div")
    # last_title = search_title_section.text.strip("\n").strip("\t")[:-1]

    # Diccionario de Datos
    data_dicts = {db:{} for db in data_blocks.keys()}

    history_blocknames = list(data_dicts.keys())
    for db in history_blocknames:
        if db == history_blocknames[0]:
            data_dicts[db]["metadata"], data_dicts[db]["info"] = get_catalog(sections)
            continue
        block = data_blocks[db]
        data_dicts[db]["metadata"], data_dicts[db]["info"] =  get_catalog(sections)

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



