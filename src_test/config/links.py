from config.parameters import DGSIAP_SECTOR

# URLS para la ingesta de datos de DGSIAP.
DGSIAP_REF = "https://nube.agricultura.gob.mx/datosAbiertos/Agricola.php"
if DGSIAP_SECTOR == "Pecuaria":
    DGSIAP_REF = "https://nube.agricultura.gob.mx/datosAbiertos/Pecuaria.php"

# Mapa de México
INEGI_MEXICO_REF = "https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/geografia/marcogeo/794551163061/mg_2025_integrado.zip"

# Conjunto de datos de Edafologia.
INEGI_EDAF_REF = "https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/geografia/"

cnie2024 = INEGI_EDAF_REF + "tematicas/Edafologia_hist/1_250_000/serie%20III/794551118313_s.zip"
cdps2013 = INEGI_EDAF_REF + "perfil/cont_nacio/1_250_000/702825266707_s.zip"
cdve2024 = INEGI_EDAF_REF + "tematicas/Edafologia_hist/1_250_000/serie%20II/794551131916_s.zip"

EDAF_API = [cnie2024, cdve2024, cdps2013]

# Conjunto de datos de Uso de Suelo.

INEGI_USO_REF = "https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/geografia/tematicas/uso_suelo/"

s2005 = INEGI_USO_REF + "1_250_000/serie_III/702825007022_s.zip"
s2009 = INEGI_USO_REF + "1_250_000/serie_IV/702825007023_s.zip"
s2013 = INEGI_USO_REF + "1_250_000/serie_V/702825007024_s.zip"
su2016 = INEGI_USO_REF + "889463173359_s.zip"
s2017 = INEGI_USO_REF + "1_250_000/serie_VI/889463598459_s.zip"
s2018 = INEGI_USO_REF + "1_250_000/serie_VII/889463842781_s.zip"

USOV_API = [s2005, s2009, s2013, su2016, s2017, s2018]


# Acceso a la API de NASA POWER
NASA_POWER_API = "https://power.larc.nasa.gov/api/temporal/daily/point"