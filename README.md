# Proyecto Agronomía

<a target="_blank" href="https://cookiecutter-data-science.drivendata.org/">
    <img src="https://img.shields.io/badge/CCDS-Project%20template-328F97?logo=cookiecutter" />
</a>

Proyecto de ciencia de datos para el análisis de factores agrícolas,
geográficos y climáticos asociados con el éxito de la producción
agrícola en los municipios de México durante el periodo **2003–2025**.

El proyecto utiliza la estructura de **Cookiecutter Data Science v2**
para mantener separadas las etapas de adquisición, procesamiento,
análisis, visualización y modelado.

---

## Pregunta de investigación

> ¿Qué factores agrícolas, geográficos y climáticos están asociados con
> el éxito de la producción de un cultivo en los municipios de México
> entre 2003 y 2025?

Como variable inicial para representar el resultado de la producción
agrícola se considera la proporción de superficie sembrada que logra
ser cosechada:

$$
TasaCosecha =
\frac{Cosechada}{Sembrada}
$$

Esta definición podrá complementarse con otras variables durante las
etapas posteriores de análisis y modelado.

---

## Periodo de estudio

El proyecto utiliza información correspondiente al periodo:

**2003–2025**

Esto representa un total de **23 años**.

---

# Fuentes de datos

El proyecto integra dos fuentes principales de información y una fuente
geográfica auxiliar.

## 1. Datos agrícolas — Secretaría de Agricultura / DGSIAP

Los datos agrícolas provienen de los datos abiertos de la
**Dirección General del Servicio de Información Agroalimentaria y
Pesquera (DGSIAP)** de la Secretaría de Agricultura.

Se utiliza un archivo para cada año del periodo 2003–2025.

Los archivos originales se almacenan en:

```text
data/raw/agricultura/
```

con una estructura como:

```text
agricola_2003.csv
agricola_2004.csv
...
agricola_2025.csv
```

Entre las principales variables disponibles se encuentran:

- año;
- estado;
- municipio;
- distrito de desarrollo rural;
- CADER;
- cultivo;
- ciclo productivo;
- modalidad de producción;
- unidad de medida;
- superficie sembrada;
- superficie cosechada;
- superficie siniestrada;
- volumen de producción;
- rendimiento;
- precio medio rural;
- valor de producción.

El esquema de los archivos presenta algunos cambios históricos que son
normalizados durante el procesamiento. Entre ellos:

```text
Nomcultivo Sin Um → Nomcultivo
Precio            → Preciomediorural
```

Los archivos originales almacenados en `data/raw/` no son modificados.

---

## 2. Datos climáticos — NASA POWER

El proyecto utiliza **NASA POWER** como fuente climática aprobada para el
dataset analítico. Se consultan datos diarios de:

- temperatura media a 2 metros (`T2M`), en grados Celsius;
- precipitación corregida (`PRECTOTCORR`), en milímetros por día.

La cobertura climática comienza en **2002**, un año antes que los datos
agrícolas. Esto permite construir correctamente el ciclo Otoño–Invierno de
2003 utilizando octubre–diciembre de 2002 y enero–marzo de 2003.

### Estrategia de descarga

NASA POWER trabaja con una cuadrícula meteorológica. Los 2,478 puntos
representativos municipales se agrupan por celda para evitar solicitudes
repetidas sobre la misma información climática.

Los resultados diarios se conservan como JSON en:

```text
data/raw/clima_nasa/
```

Estos archivos funcionan como caché reanudable:

- un JSON completo no se vuelve a descargar;
- una interrupción de Internet no obliga a reiniciar todo el proceso;
- la escritura se realiza primero en un archivo temporal;
- el archivo definitivo aparece únicamente después de terminar la respuesta.

La descarga utiliza reintentos con espera progresiva para errores temporales
de conexión, límites de solicitudes y respuestas HTTP recuperables.

### Dataset climático mensual

Los datos diarios se agregan por municipio, año y mes. Para cada mes se
calcula:

```text
temperatura_media_mes_c = promedio de T2M
precipitacion_mes_mm     = suma de PRECTOTCORR
```

Un valor mensual solamente se acepta cuando están disponibles todos los días
esperados del mes. También se conservan `dias_esperados`,
`dias_temperatura` y `dias_precipitacion` para comprobar la cobertura.

El producto climático analítico base es:

```text
data/processed/clima_nasa/clima_municipal_mensual_2002_2025.csv
```

Su llave única es:

```text
cvegeo + anio + mes
```

El archivo contiene **713,664 registros**:

```text
2,478 municipios × 24 años × 12 meses
```

El dataset mensual se mantiene independiente porque permite construir sin una
nueva descarga:

- trimestres calendario;
- estaciones meteorológicas;
- ventanas móviles;
- periodos de siembra, floración o cosecha;
- agregaciones específicas por cultivo;
- ciclos Otoño–Invierno, Primavera–Verano y Perennes.

El antiguo consolidado anual puede conservarse como producto derivado, pero
el archivo mensual es la fuente climática procesada de mayor granularidad.

### Ejecución del flujo climático

1. Abrir `notebooks/descarga_clima_nasa.ipynb`.
2. Preparar los puntos representativos municipales de INEGI.
3. Ejecutar la agregación con `EJECUTAR_AGREGACION_MENSUAL = True`.
4. Validar las 12 observaciones mensuales por municipio y año.
5. Cambiar la bandera a `False` después de generar el CSV.
6. Ejecutar `notebooks/integracion_agricultura_clima.ipynb`.

La integración no une directamente las 12 filas mensuales con cada registro
agrícola, porque eso multiplicaría las observaciones. Primero transforma los
meses a columnas y después calcula temperatura media y precipitación acumulada
para el ciclo productivo correspondiente.

---

## 3. Información geográfica auxiliar — INEGI

Para relacionar los municipios agrícolas con la información climática
se utilizan geometrías municipales obtenidas del
**Instituto Nacional de Estadística y Geografía (INEGI)**.

A partir de cada geometría municipal se calcula un punto representativo.
Las geometrías se proyectan para calcular dicho punto y posteriormente
las coordenadas se transforman nuevamente a **EPSG:4326**.

Las coordenadas resultantes se almacenan en:

```text
data/interim/inegi/municipios_coordenadas_inegi.csv
```

Se identificaron:

- **2,478 municipios** en la información geográfica de INEGI;
- **2,452 municipios** presentes en los datos agrícolas de 2003–2025;
- **0 municipios agrícolas sin coordenadas** después de la integración.

La adquisición climática se realizó para los **2,478 municipios** disponibles
en la capa nacional. La integración agrícola utiliza el subconjunto de claves
municipales presente en los registros de producción.

---

# Integración de las fuentes

El flujo general de datos del proyecto es:

```text
Secretaría de Agricultura
        |
        |  datos agrícolas 2003–2025
        v
Registros agrícolas
        |
        | Idestado + Idmunicipio + Anio
        |
        +--------------------------------+
                                         |
INEGI                                    |
Geometrías municipales                   |
        |                                |
        v                                |
Coordenadas representativas              |
        |                                |
        v                                |
NASA POWER                               |
Datos diarios 2002–2025                  |
        |                                |
        v                                |
Agregación municipio-año-mes             |
        |                                |
        +--------------------------------+
                     |
                     v
       Ventanas según ciclo productivo
                     |
                     v
          Dataset analítico integrado
                     |
                     v
              data/processed/
```

La tabla mensual utiliza la llave:

```text
cvegeo + anio + mes
```

Antes de la integración, los meses se convierten a características y se
construyen ventanas climáticas coherentes con `Nomcicloproductivo`:

- Otoño–Invierno: octubre–diciembre anterior y enero–marzo actual;
- Primavera–Verano: abril–septiembre actual;
- Perennes: enero–diciembre actual.

La unión final usa `cvegeo`, `Anio` y el ciclo productivo, con validación
`many_to_one`. Las observaciones agrícolas conservan además cultivo,
modalidad, superficies y variables de producción.

---

# Procesamiento agrícola

Los archivos agrícolas históricos presentan diferencias de esquema y
formato entre distintos años.

El pipeline implementado en `proyecto_agronomia/features.py` realiza:

1. lectura de los archivos originales;
2. normalización de nombres de columnas;
3. conversión de variables cuantitativas;
4. integración de los 23 archivos anuales;
5. generación de variables derivadas;
6. creación de indicadores de calidad.

El conjunto histórico construido contiene:

- **825,089 observaciones**;
- **23 años**;
- periodo **2003–2025**.

El dataset agrícola procesado se almacena en:

```text
data/processed/agricultura_features.csv
```

---

# Variable `TasaCosecha`

La primera variable derivada utilizada para representar el resultado
agrícola es:

\[
TasaCosecha =
\frac{Cosechada}{Sembrada}
\]

Cuando `Sembrada = 0`, el valor de `TasaCosecha` se conserva como
faltante para evitar una división indefinida.

No se corrigen ni eliminan automáticamente las observaciones
potencialmente inconsistentes.

En su lugar se generan los indicadores:

```text
FlagSembradaCero
FlagCosechadaMayorSembrada
FlagBalanceSuperficie
```

Esto permite conservar los datos originales y tomar posteriormente
decisiones explícitas durante el análisis o modelado.

---

# Reglas de calidad

Durante el procesamiento se verifican, entre otros aspectos:

- archivos y años disponibles;
- duplicados;
- valores faltantes;
- valores negativos;
- consistencia de identificadores geográficos;
- disponibilidad de coordenadas;
- cobertura temporal;
- tipos de las variables numéricas;
- número esperado de años por municipio;
- superficie cosechada mayor que superficie sembrada;
- balance entre superficie sembrada, cosechada y siniestrada;
- compatibilidad de unidades antes de realizar agregaciones.

Los valores faltantes no son eliminados automáticamente.

Asimismo, el volumen de producción no debe agregarse
indiscriminadamente entre observaciones que utilicen unidades de medida
incompatibles.

---

# Notebooks

Las notebooks funcionan como interfaces reproducibles del pipeline.

La lógica principal no se duplica dentro de ellas; las operaciones de
adquisición y transformación se importan desde el paquete
`proyecto_agronomia`.

Entre las notebooks de adquisición se encuentran:

```text
notebooks/
├── descarga_agricola.ipynb
├── descarga_clima_conagua.ipynb
└── descarga_clima_nasa.ipynb
```

`descarga_agricola.ipynb` documenta:

```text
Descarga
   ↓
Normalización
   ↓
Histórico 2003–2025
   ↓
Variables derivadas
   ↓
Validación
```

`descarga_clima_nasa.ipynb` documenta:

```text
Municipios de INEGI
        ↓
Puntos representativos
        ↓
Agrupación por celda NASA POWER
        ↓
JSON diarios reanudables
        ↓
Agregación mensual 2002–2025
        ↓
Validación municipio-año-mes
```

La lógica reutilizable se encuentra en:

```text
proyecto_agronomia/datasets/clima_nasa.py
```

La integración posterior se ejecuta en:

```text
notebooks/integracion_agricultura_clima.ipynb
```

---

# Reproducibilidad

## Crear el entorno virtual

```bash
python -m venv .venv
```

En Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

## Instalar dependencias

```bash
pip install -r requirements.txt
```

El proyecto se instala como paquete editable mediante la entrada:

```text
-e .
```

incluida en `requirements.txt`.

Esto permite utilizar las funciones del proyecto directamente desde
las notebooks:

```python
from proyecto_agronomia.dataset import descargar_datos_agricolas

from proyecto_agronomia.features import (
    construir_historico_agricola,
    generar_features_agricolas,
)
```

---

# Objetivo de modelado

Una etapa posterior utilizará técnicas estadísticas y de aprendizaje
automático para estudiar la relación entre las características
agrícolas y climáticas y los resultados de producción.

Una variable objetivo candidata es:

```text
TasaCosecha = Cosechada / Sembrada
```

Entre las posibles variables explicativas se encuentran:

- cultivo;
- año;
- ciclo productivo;
- modalidad;
- municipio;
- estado;
- temperatura;
- precipitación;
- evapotranspiración;
- otras variables derivadas durante el análisis exploratorio.

La selección definitiva de variables y modelos se realizará después de
completar la integración, el análisis exploratorio y la evaluación de
posibles problemas de fuga de información.



# Project Organization

```text
├── LICENSE                 <- Open-source license
├── Makefile                <- Commands for reproducible project workflows
├── README.md               <- Project documentation
├── requirements.txt        <- Python dependencies
├── pyproject.toml          <- Package and tool configuration
│
├── data/
│   ├── external/           <- Data from third-party sources
│   ├── interim/            <- Intermediate transformed data
│   │   ├── agricultura_historica.csv
│   │   └── inegi/
│   │       ├── municipios_mexico_inegi.geojson
│   │       ├── estados_mexico_inegi.geojson
│   │       └── municipios_coordenadas_inegi.csv
│   │
│   ├── processed/          <- Canonical datasets for analysis/modeling
│   │   ├── agricultura_features.csv
│   │   ├── agricultura_clima_2003_2025.csv
│   │   └── clima_nasa/
│   │       └── clima_municipal_mensual_2002_2025.csv
│   │
│   └── raw/                <- Original immutable data
│       ├── agricultura/
│       │   ├── agricola_2003.csv
│       │   ├── ...
│       │   └── agricola_2025.csv
│       │
│       ├── clima/
│       │   └── conagua/
│       └── clima_nasa/
│           ├── nasa_celda_*.json
│           └── nasa_?????_2023_2025.json
│
├── docs/
│
├── models/                 <- Trained models and predictions
│
├── notebooks/              <- Reproducible Jupyter notebooks
│   ├── descarga_agricola.ipynb
│   ├── descarga_clima_conagua.ipynb
│   ├── descarga_clima_nasa.ipynb
│   ├── integracion_agricultura_clima.ipynb
│   └── analisis_exploratorio.ipynb
│
├── references/             <- Data dictionaries and supporting material
│
├── reports/
│   └── figures/            <- Generated figures
│
├── tests/
│
└── proyecto_agronomia/     <- Reusable Python source code
    ├── __init__.py
    ├── config.py            <- Paths and project configuration
    ├── dataset.py           <- Data acquisition
    ├── datasets/
    │   └── clima_nasa.py    <- NASA POWER download and aggregation
    ├── features.py          <- Transformations and feature engineering
    ├── plots.py             <- Visualization functions
    │
    └── modeling/
        ├── __init__.py
        ├── train.py         <- Model training
        └── predict.py       <- Model inference
```

---

## Licencia

Este proyecto se distribuye bajo la licencia incluida en
[`LICENSE`](LICENSE).
