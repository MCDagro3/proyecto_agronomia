from scripts.config import dgsiap_api
from scripts.File import File
import os
from datetime import date
import requests
import yarl


def get_filename(link):
    head = requests.head(link)
    for v in head.headers.values():
        try:
            if v.index("filename"):
                name=v.split("filename=")[-1]
                name=name[1:-1]
                break
        except:
            pass
    return name

    
def parse_link(url, base=dgsiap_api):
    y_url= yarl.URL(url)
    link = base.with_query(y_url.query)
    return link


def download(link, filename, path, **kwargs):
    hint = kwargs.get("hint", 0)
    filepath = path / filename
    if hint:
        check = input(f"El archivo {filename} se guardara en {filepath}.\n¿Deseas continuar? Responda NO si quiere cancelar la descarga")
        if check == "NO":
            print("Revise el archivo a descargar\n y/o la ruta donde guardarlos en dgsiap.py")
    print(link, filename, path, filepath)
    if not os.path.exists(filepath):
        try:
            response = requests.get(link, stream=True)
        except:
            print(f"Error. Status Code {response.status_code}")
        print("La conexión procedio. Comenzamos con la descarga")
        with response as data:
            with open(filepath, "wb") as f:
                f.write(data.content)
        print(f"Archivo {filename} descargado correctamente")
        print(f"Descargado el {date.today()}")
        print(f"Se encuentra en {str(filepath).split("..")[-1]}")
    else:
        print(f"El archivo ya fue descargado. Se encuentra en {str(filepath).split("..")[-1]}")


def input_parser(value):
    """
        Elementos string, int o list los coniverte a lista
    """
    if not type(value)==list:
        assert type(value)==str or type(value)==int, "Revisa tu entrada"
        value = [value]
    try:
        list_value = [str(v) for v in value]
    except:
        print("Revisa tu seleccion")
    return list_value


def year_checker(category, period, **kwargs):
    """
        Si la dejas en blanco considerara todos los años disponibles
    """
    raw_data = kwargs.get("ref", None)
    assert category in raw_data.keys(), "La categoria no existe"
    query_year_f = kwargs.get("year_column", "ANIO")
    subset = raw_data[category]['Datasets']
    if period!="*":
        years = input_parser(period)
        selection = {y: [] for y in years}
        for url in subset:
            query_year = url.query[query_year_f]
            if query_year in set(years):
                selection[query_year].append(url)
    else:
        selection = {url.query[query_year_f]: url for url in subset}
    return selection


def get_dictlink(category, period, **kwargs):
    request = {}
    raw_data = kwargs.get("ref", None)
    category = raw_data.keys() if category == "*" else input_parser(category)
    period = input_parser(period) if period!= "*" else "*"
    for c in category:
        assert c in raw_data.keys(), "Revisa tus categorias"
        dict_cat = raw_data[c]['Metadata']['info']['download']
        data_cat = year_checker(c, period, **kwargs)
        req_cat = {"Codebook":dict_cat, "Data":data_cat}
        request[c] = req_cat
    return request


def get_request(**kwargs):
    dreq = kwargs.get("request", "*")
    if dreq == "*":
        return get_dictlink("*", "*")
    assert set(dreq.keys()) == set(["category", "period"]), "Revisa tu solicitud"
    dclink = get_dictlink(category=dreq['category'], period=dreq['period'], **kwargs)
    return dclink


def agro_files(req):
    downlog = {}
    for block in req.keys():
        down_block = {"Codebook": None,
                      "Data": {}}
        req_block = req[block]
        for dt in req_block.keys():
            dt_block = req_block[dt]
            dt_block = {block: dt_block} if type(dt_block) == str else dt_block
            for par, url in dt_block.items():
                link = parse_link(url)
                filename = get_filename(link)
                if len(par)== 4:
                    down_block["Data"][par] = File(link, filename, source="dgsiap")
                else:
                    down_block['Codebook'] = File(link, filename, source="dgsiap")
        downlog[block] = down_block
    return downlog


def agro_project():
    from scripts.dgsiap import dict_master
    raw_data = dict_master()
    project_request= {"category": "Municipal", "period": "*"}
    response = get_request(request=project_request, ref=raw_data)
    agro = agro_files(response)
    return agro


def load_filetree(ftree):
    """
        Download the files of a file tree.
    """
    for v in ftree.values():
        v['Codebook'].downcheck()
        data_file = v['Data']
        for dv in data_file.values():
            dv.downcheck()
