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

\[
TasaCosecha =
\frac{Cosechada}{Sembrada}
\]

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

## 2. Datos climáticos — Open-Meteo Historical Weather API

La segunda fuente principal corresponde a información climática
histórica obtenida mediante **Open-Meteo Historical Weather API**,
utilizando el modelo/reanálisis **ERA5**.

El periodo de consulta es igualmente **2003–2025**.

Para cada municipio agrícola se consultan datos diarios de:

- temperatura media a 2 m;
- temperatura máxima a 2 m;
- temperatura mínima a 2 m;
- precipitación acumulada;
- horas de precipitación;
- evapotranspiración de referencia ET₀ (FAO).

Los datos diarios son posteriormente agregados por municipio y año,
obteniendo:

- temperatura media anual;
- temperatura máxima anual;
- temperatura mínima anual;
- precipitación anual;
- número de días con lluvia;
- horas de precipitación;
- evapotranspiración anual.

Debido al volumen de información solicitado y a los límites de la API,
la descarga se realiza por entidad federativa y en pequeños lotes de
municipios.

Los resultados se almacenan progresivamente en:

```text
data/raw/clima/
```

Ejemplo:

```text
clima_01_aguascalientes.csv
clima_02_baja_california.csv
clima_03_baja_california_sur.csv
...
clima_32_zacatecas.csv
```

El pipeline utiliza checkpoints por estado. Si un municipio ya cuenta
con los 23 años esperados, sus datos no se solicitan nuevamente.

Esto permite reanudar una descarga interrumpida sin perder el progreso
obtenido anteriormente.

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

Por lo tanto, el universo objetivo para la adquisición climática está
formado por **2,452 municipios agrícolas**.

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
Open-Meteo / ERA5                        |
Clima diario 2003–2025                   |
        |                                |
        v                                |
Agregación municipio-año                 |
        |                                |
        +--------------------------------+
                     |
                     v
          Dataset analítico integrado
                     |
                     v
              data/processed/
```

La integración agrícola-climática utiliza principalmente la llave:

```text
Anio
Idestado
Idmunicipio
```

Las observaciones agrícolas mantienen además sus dimensiones propias,
como cultivo, ciclo productivo y modalidad.

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
└── descarga_clima.ipynb
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

`descarga_clima.ipynb` documenta:

```text
Municipios agrícolas
        ↓
Coordenadas INEGI
        ↓
Open-Meteo / ERA5
        ↓
Agregación anual
        ↓
Validación
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
│   │   └── agricultura_features.csv
│   │
│   └── raw/                <- Original immutable data
│       ├── agricultura/
│       │   ├── agricola_2003.csv
│       │   ├── ...
│       │   └── agricola_2025.csv
│       │
│       └── clima/
│           ├── clima_01_aguascalientes.csv
│           ├── ...
│           └── clima_32_zacatecas.csv
│
├── docs/
│
├── models/                 <- Trained models and predictions
│
├── notebooks/              <- Reproducible Jupyter notebooks
│   ├── descarga_agricola.ipynb
│   └── descarga_clima.ipynb
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