# Conjunto de parámetros previos a la descarga
# NO MODIFICAR. Si la prioridad es el analisis sobre la proucción agricola 

from datetime import datetime

# DGSIAP
DGSIAP_SECTOR = "Agricola"  # Tambien es posible considerar el pecuario.
DGSIAP_CATEGORY = "Municipal" # El DGSIAP considera 3 tipos de datos. 

# INEGI
PREPROCESS_CRS = 6372

# MAPBIOMAS
MAPBIOMAS_PERIOD = list(range(2000, 2026))


# NASA POWER
## API Range
DATE_DELIMITER = "-"
DATE_STRUCTURE = f"%d{DATE_DELIMITER}%m{DATE_DELIMITER}%Y"
PERIOD = ("01-01-2002", "31-12-2026")
assert datetime.strptime(PERIOD[0], DATE_STRUCTURE).strftime(DATE_STRUCTURE) == PERIOD[0], "Mantenga el formato de fecha definido"
assert datetime.strptime(PERIOD[1], DATE_STRUCTURE).strftime(DATE_STRUCTURE) == PERIOD[1], "Mantenga el formato de fecha definido"

## API Preset
COMMUNITY = "ag" 
HEADER = True
UNITS = "metric"
FORMAT = "json"


def base_query(period, point, parameters):
    lon, lat = point
    start, end = period
    query = {
    "start": start,
    "end": end,
    "latitude": lat,
    "longitude": lon,
    "community": COMMUNITY,
    "parameters": ",".join(parameters),
    "format": FORMAT
    }
    return query





