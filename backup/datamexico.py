"""
    Descarga de Datos de la API de Datos México

"""
from scripts.config import DATA_MEXICO
import requests


def build_request(data, opts, msres):
    api_sep = ","
    api = DATA_MEXICO
    drilldowns = api_sep.join(opts)
    measures = api_sep.join(msres)
    link = api.with_query(cube=data, drilldowns=drilldowns, measures=measures)
    return link


def api(req):
    response = requests.get(req, stream=True)
    print(response.status_code)
    if response.status_code == 200:
        data_js = response.json()
    else:
        data_js = -1
    return data_js