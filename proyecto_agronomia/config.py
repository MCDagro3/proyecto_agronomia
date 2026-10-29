from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file if it exists
load_dotenv()

# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------

PROJ_ROOT = Path(__file__).resolve().parents[1]
logger.info(f"PROJ_ROOT path is: {PROJ_ROOT}")

DATA_DIR = PROJ_ROOT / "data"

RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"

MODELS_DIR = PROJ_ROOT / "models"

REPORTS_DIR = PROJ_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

# ---------------------------------------------------------------------
# Project data directories
# ---------------------------------------------------------------------

AGRICULTURA_RAW_DIR = RAW_DATA_DIR / "agricultura"
CLIMA_RAW_DIR = RAW_DATA_DIR / "clima"
REFERENCES_DIR = PROJ_ROOT / "references"
CONAGUA_RAW_DIR = CLIMA_RAW_DIR / "conagua"

INEGI_INTERIM_DIR = INTERIM_DATA_DIR / "inegi"
EDAFOLOGIA_RAW_DIR = RAW_DATA_DIR / "edafologia"
EDAFOLOGIA_REFERENCES_DIR = REFERENCES_DIR / "edafologia"
# ---------------------------------------------------------------------
# Study period
# ---------------------------------------------------------------------

ANIO_INICIAL = 2003
ANIO_FINAL = 2025

ANIOS = list(range(ANIO_INICIAL, ANIO_FINAL + 1))

# ---------------------------------------------------------------------
# Data source URLs
# ---------------------------------------------------------------------

AGRICULTURA_URL_TEMPLATE = (
    "https://nube.agricultura.gob.mx/index.php"
    "?view=10AE434F-A2158368-A120BC5A-EDF4AFAA&ANIO={anio}"
)

AGRICULTURA_DICCIONARIO_URL = (
    "https://nube.agricultura.gob.mx/"
    "index.php?view=5D24F995-E734D711-1EA6F8D2-9D1387D7"
)

AGRICULTURA_DICCIONARIO_PATH = (
    REFERENCES_DIR
    / "diccionario_datos_agricultura_dgsiap.xlsx"
)

INEGI_MUNICIPIOS_URL_TEMPLATE = (
    "https://gaia.inegi.org.mx/"
    "wscatgeo/v2/geo/mgem/{clave_estado}"
)

INEGI_ESTADOS_URL_TEMPLATE = (
    "https://gaia.inegi.org.mx/"
    "wscatgeo/v2/geo/mgee/{clave_estado}"
)

EDAFOLOGIA_URL = (
    "https://www.inegi.org.mx/contenidos/productos/"
    "prod_serv/contenidos/espanol/bvinegi/productos/"
    "geografia/tematicas/Edafologia_hist/1_250_000/"
    "serie%20III/794551118313_s.zip"
)

EDAFOLOGIA_DICCIONARIO_URL = (
    "https://www.inegi.org.mx/contenidos/productos/"
    "prod_serv/contenidos/espanol/bvinegi/productos/"
    "nueva_estruc/702825092023.pdf"
)

EDAFOLOGIA_DICCIONARIO_PATH = (
    EDAFOLOGIA_REFERENCES_DIR
    / "diccionario_datos_edafologicos_250k_v4.pdf"
)

CONAGUA_KMZ_PATH = (
    CONAGUA_RAW_DIR / "EstacionesClimatologicas.kmz"
)
CONAGUA_KMZ_URL = (
    "https://smn.conagua.gob.mx/tools/GUI/estaciones-climatologicas/data/EstacionesClimatologicas.kmz"
)
CONAGUA_INTERIM_DIR = (
    INTERIM_DATA_DIR / "clima" / "conagua"
)

CONAGUA_PROCESSED_DIR = (
    PROCESSED_DATA_DIR / "clima" / "conagua"
)

CONAGUA_ANIO_INICIAL = 1981
CONAGUA_ANIO_FINAL = 2025

CONAGUA_DISTANCIA_MIN_KM = 50

CONAGUA_MEXICO_GEOJSON_URL = (
    "https://www.geoboundaries.org/api/current/"
    "gbOpen/MEX/ADM0/"
)

# ============================================================
# NASA POWER - Datos climáticos históricos
# ============================================================

# API oficial de NASA POWER
NASA_POWER_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
)

# Directorios de almacenamiento
NASA_POWER_RAW_DIR = RAW_DATA_DIR / "clima_nasa"
NASA_POWER_PROCESSED_DIR = PROCESSED_DATA_DIR / "clima_nasa"

# Periodo climático completo del proyecto
NASA_POWER_ANIO_INICIAL = 2003
NASA_POWER_ANIO_FINAL = 2025

# Parámetros meteorológicos
NASA_POWER_PARAMETROS = [
    "T2M",          # Temperatura media a 2 metros (°C)
    "PRECTOTCORR",  # Precipitación corregida (mm/día)
]

# Configuración de las solicitudes
NASA_POWER_COMMUNITY = "AG"
NASA_POWER_FORMAT = "JSON"
NASA_POWER_TIMEOUT = 120

# Control de solicitudes para evitar errores HTTP 429
NASA_POWER_PAUSA = 3
NASA_POWER_MAX_REINTENTOS = 5

ESTADOS = {
    1: "aguascalientes",
    2: "baja_california",
    3: "baja_california_sur",
    4: "campeche",
    5: "coahuila",
    6: "colima",
    7: "chiapas",
    8: "chihuahua",
    9: "ciudad_de_mexico",
    10: "durango",
    11: "guanajuato",
    12: "guerrero",
    13: "hidalgo",
    14: "jalisco",
    15: "mexico",
    16: "michoacan",
    17: "morelos",
    18: "nayarit",
    19: "nuevo_leon",
    20: "oaxaca",
    21: "puebla",
    22: "queretaro",
    23: "quintana_roo",
    24: "san_luis_potosi",
    25: "sinaloa",
    26: "sonora",
    27: "tabasco",
    28: "tamaulipas",
    29: "tlaxcala",
    30: "veracruz",
    31: "yucatan",
    32: "zacatecas",
}
# ---------------------------------------------------------------------
# Analysis constants
# ---------------------------------------------------------------------

TOP_N = 15

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------

# If tqdm is installed, configure loguru with tqdm.write
# https://github.com/Delgan/loguru/issues/135
try:
    from tqdm import tqdm

    logger.remove(0)
    logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True)

except ModuleNotFoundError:
    pass
