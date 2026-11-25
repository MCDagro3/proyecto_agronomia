# Descarga NASA POWER.
from config.parameters import base_query, PERIOD, DATE_STRUCTURE
from config.links import NASA_POWER_API
from config.paths import datapaths
from datetime import datetime
from yarl import URL
import json
import requests

# Carpeta donde guardaremos lo obtenido por la API.
output = datapaths['pure']['NASAPOWER']

nasa = URL(NASA_POWER_API)

point = (-10, 10)
parameters = ["T2M", "PRECTOTCORR"]


def query(period, point, parameters, base = base_query):
    start, end = period
    obj_start = datetime.strptime(start, DATE_STRUCTURE)
    obj_end = datetime.strptime(end, DATE_STRUCTURE)
    api_start = obj_start.strftime("%Y%m%d")
    api_end = obj_end.strftime("%Y%m%d")
    api_period = (api_start, api_end)
    format_query = base(api_period, point, parameters)
    return format_query

req = query(PERIOD, point, parameters)

def get_nasa(query, savepath = output / f"{PERIOD[0]}_{PERIOD[1]}_T2MPREP.json"):
    request = nasa.with_query(query)
    response = requests.get(str(request))
    result = response.json()
    savepath.write_text(json.dumps(result, ensure_ascii=False, indent=4), encoding="utf-8")
    print(f"Archivo generado {savepath}")


