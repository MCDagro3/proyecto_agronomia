from scripts.config import dgsiap, DATA_FOLDERS
import os
from datetime import date
import requests
import yarl


def get_filename(link):
    head = requests.head(link)
    for u, v in head.headers.items():
        try:
            if v.index("filename"):
                name=v.split("filename=")[-1]
                name=name[1:-1]
                break
        except:
            pass
    return name

    
def parse_link(url, base=dgsiap):
    y_url= yarl.URL(url)
    link = base.with_query(y_url.query)
    return link


def download(link, filename, path=DATA_FOLDERS['external'], **kwargs):
    hint = kwargs.get("hint", 0)
    filelink = link / filename
    filepath = path / filename
    if hint:
        check = input(f"El archivo {filename} se guardara en {filepath}.\n¿Deseas continuar? Responda NO si quiere cancelar la descarga")
        if check == "NO":
            print("Revise el archivo a descargar\n y/o la ruta donde guardarlos en dgsiap.py")
    if not os.path.exists(filepath):
        try:
            odata = requests.get(link)
        except e:
            print(f"Error {e}. Status Code {odata.status_code}")
        print("La conexión procedio. Comenzamos con la descarga")
        with odata as data:
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
    except e:
        print(e, "Revisa tu seleccion")
    return list_value


def year_checker(category, period, **kwargs):
    """
        Si la dejas en blanco considerara todos los años disponibles
    """
    raw_data = kwargs.get("ref", None)
    assert category in raw_data.keys(), "La categoria no existe"
    y_c = kwargs.get("year_column", "ANIO")
    unique = kwargs.get("deep", False)
    years = input_parser(period)
    selection = {y: [] for y in years}
    subset = raw_data[category]['Datasets']
    for y in years:
            for url in subset:
                checker = 1 if str(y)==url.query['ANIO'] else 0
                if checker:
                    selection[y].append(url)
                    if unique:
                        break
    return selection


def selector(category, period, **kwargs):
    raw_data = kwargs.get("ref", None)
    selection = {}
    category = input_parser(category)
    for c in category:
        assert c in raw_data.keys(), "Revisa tus categorias"
    for cat in category:
        selection[cat] = year_checker(cat, period, **kwargs)
    return selection


def down_arq(category, period, **kwargs):
    raw_data = kwargs.get("ref", None)
    request = {}
    category = input_parser(category)
    for c in category:
        assert c in raw_data.keys(), "Revisa tus categorias"
        dict_cat = raw_data[c]['Metadata']['info']['download']
        data_cat = selector(category, period, **kwargs)
        req_cat = {"Codebook":dict_cat,
                    "Datasets":data_cat[c]}
        request[c] = req_cat
    return request


def full_cat(category, **kwargs):
    """
        Descargar una categoria completa.
    """
    raw_data = kwargs.get("ref", None)
    category = input_parser(category)
    for c in category:
        assert c in raw_data.keys(), "Revisa las categorias"
    response = {}
    for c in category:
        cat_code = raw_data[c]['Metadata']['info']['download']
        cat_data = raw_data[c]['Datasets']
        year_data = {du.query['ANIO']: du for du in cat_data}
        response[c] = {"Codebook": cat_code, "Data":year_data}
    return response


def downassist(**kwargs):
    """
        Descarga arbitraria de información del DGSIAP
    """
    raw_data = kwargs.get("ref", None)
    request = kwargs.get("request", "*")
    response = None
    if request == "*":
        response = full_cat(list(raw_data.keys()), **kwargs)
        return response
    assert set(request.keys()) == set(["category", "period"]), "Revisa tu solicitud"
    cats = input_parser(request['category'])
    years = input_parser(request['period'])
    if cats[0]=="*":
        response ={}
        for c in raw_data.keys():
            response[c]=down_arq(c, years, **kwargs)[c]
        return response
    if years[0] == "*":
        response = full_cat(cats, **kwargs)
    else:
        response = down_arq(cats, years, **kwargs)
    return response


def downbot(dictlink, **kwargs):
    all_links = []
    all_fns = []
    for cat, dicl in dictlink.items():
        for lv, urls in dicl.items():
            if not type(urls) == dict:
                link = parse_link(urls)
                fn = get_filename(link)
                all_links.append(link)
                all_fns.append(fn)
            else:
                for url in urls.values():
                    link = parse_link(url)
                    fn = get_filename(link)
                    all_links.append(link)
                    all_fns.append(fn)                    
        for k in range(len(all_links)):
            download(all_links[k], all_fns[k])


def agro(**kwargs):
    down_data = {}
    data = downassist()
    for block, seturl in data.items():
        for dt, url in seturl.items():
            if not type(url)==list:
                link = parse_link(url)
                fn = get_filename(link)
                if block != "No segumiento":
                    fn = f"{block[:2]}_{fn}"
                down_data[fn] = link
            else:
                links = [parse_link(u) for u in url]
                fns = [get_filename(l) for l in links]
                for k in range(len(links)):
                    down_data[fns[k]] = links[k]
        for name, link in down_data.items():
            download(link, name, **kwargs)
