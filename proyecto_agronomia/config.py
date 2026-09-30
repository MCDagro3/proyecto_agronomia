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

INEGI_INTERIM_DIR = INTERIM_DATA_DIR / "inegi"

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

OPEN_METEO_ARCHIVE_URL = (
    "https://archive-api.open-meteo.com/v1/archive"
)

INEGI_MUNICIPIOS_URL_TEMPLATE = (
    "https://gaia.inegi.org.mx/"
    "wscatgeo/v2/geo/mgem/{clave_estado}"
)

INEGI_ESTADOS_URL_TEMPLATE = (
    "https://gaia.inegi.org.mx/"
    "wscatgeo/v2/geo/mgee/{clave_estado}"
)

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