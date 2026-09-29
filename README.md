# Proyecto de análisis agrícola y climático de México

Proyecto de ciencia de datos orientado al análisis de la producción agrícola en México durante el periodo **2003–2025**, integrando información agrícola, geográfica y climática.

El objetivo es construir un conjunto de datos longitudinal a nivel municipal que permita estudiar la relación entre las condiciones productivas, geográficas y climáticas y los resultados de la actividad agrícola.

## Pregunta de investigación

> ¿Qué factores agrícolas, geográficos y climáticos están asociados con el éxito de la producción de un cultivo en los municipios de México entre 2003 y 2025?

Como variable inicial para representar el resultado de la producción agrícola se considera la proporción de superficie sembrada que logra ser cosechada:

\[
TasaCosecha =
\frac{Cosechada}{Sembrada}
\]

Esta definición podrá complementarse con otras variables durante las etapas de análisis y modelado.

---

## Periodo de análisis

El proyecto utiliza información correspondiente a:

**2003–2025**

Esto representa un periodo de **23 años**.

---

# Fuentes de datos

El proyecto integra dos fuentes principales de información y una fuente geográfica auxiliar.

## 1. Datos agrícolas — Secretaría de Agricultura / DGSIAP

Los datos agrícolas provienen de los datos abiertos de la **Dirección General del Servicio de Información Agroalimentaria y Pesquera (DGSIAP)** de la Secretaría de Agricultura.

Los archivos se descargan anualmente para el periodo 2003–2025.

Patrón utilizado para la descarga:

```text
https://nube.agricultura.gob.mx/index.php?view=10AE434F-A2158368-A120BC5A-EDF4AFAA&ANIO={anio}
```

Los archivos originales se almacenan en:

```text
data/raw/
```

con la estructura:

```text
agricola_2003.csv
agricola_2004.csv
...
agricola_2025.csv
```

Entre las variables disponibles se encuentran:

- año
- estado
- municipio
- distrito de desarrollo rural
- CADER
- cultivo
- ciclo productivo
- modalidad de producción
- unidad de medida
- superficie sembrada
- superficie cosechada
- superficie siniestrada
- volumen de producción
- rendimiento
- precio medio rural
- valor de producción

El esquema de los archivos presenta algunos cambios históricos que son normalizados durante el procesamiento. Entre ellos:

- `Nomcultivo` / `Nomcultivo Sin Um`
- `Precio` / `Preciomediorural`

Los archivos originales no son modificados.

---

## 2. Datos climáticos — Open-Meteo Historical Weather API

La segunda fuente principal corresponde a información climática histórica obtenida mediante **Open-Meteo Historical Weather API**, utilizando datos del modelo/reanálisis **ERA5**.

El periodo consultado es igualmente:

**2003–2025**

Para cada municipio agrícola se obtienen datos diarios de:

- temperatura media a 2 m
- temperatura máxima a 2 m
- temperatura mínima a 2 m
- precipitación acumulada
- horas de precipitación
- evapotranspiración de referencia ET₀ (FAO)

Los datos diarios son posteriormente agregados por municipio y año para generar variables como:

- temperatura media anual
- temperatura máxima anual
- temperatura mínima anual
- precipitación anual
- número de días con lluvia
- horas de precipitación
- evapotranspiración anual

Debido al volumen de información solicitado y a los límites de la API, las consultas se realizan en pequeños lotes de municipios.

Los resultados se almacenan progresivamente por estado en:

```text
data/raw_clima/
```

Ejemplo:

```text
clima_01_aguascalientes.csv
clima_02_baja_california.csv
clima_03_baja_california_sur.csv
...
clima_32_zacatecas.csv
```

El proceso es reanudable: si un municipio o estado ya cuenta con información completa, se evita realizar nuevamente la consulta correspondiente.

---

## 3. Información geográfica auxiliar — INEGI

Para vincular los municipios agrícolas con información climática se utiliza información geográfica del **Instituto Nacional de Estadística y Geografía (INEGI)**.

Se obtuvieron las geometrías municipales de las 32 entidades federativas de México.

A partir de cada geometría municipal se calculó un punto representativo, utilizado posteriormente como coordenada de consulta para Open-Meteo.

Las coordenadas municipales procesadas se almacenan en:

```text
data/interim/municipios_coordenadas_inegi.csv
```

Se identificaron:

- **2,478 municipios** en la información geográfica de INEGI.
- **2,452 municipios** presentes en los datos agrícolas de 2003–2025.
- **0 municipios agrícolas sin coordenadas geográficas** después de la integración.

Por lo tanto, el conjunto climático objetivo contiene información para **2,452 municipios agrícolas**.

---

# Integración de las fuentes

El flujo general de integración es:

```text
Secretaría de Agricultura
        |
        |  Datos agrícolas 2003–2025
        v
Municipio + Año + Cultivo
        |
        |
        +---------------------------+
                                    |
INEGI                               |
Geometrías municipales              |
        |                           |
        v                           |
Coordenadas representativas         |
        |                           |
        v                           |
Open-Meteo / ERA5                   |
Clima diario 2003–2025              |
        |                           |
        v                           |
Agregación municipio-año            |
        |                           |
        +---------------------------+
                    |
                    v
           Dataset integrado
                    |
                    v
        data/processed/tidy.csv
```

La integración final se realiza principalmente mediante:

```text
Idestado
Idmunicipio
Anio
```

permitiendo asociar las condiciones climáticas anuales con las observaciones agrícolas correspondientes.

---

# Estructura del proyecto

```text
proyecto_agronomia/
│
├── data/
│   ├── raw/
│   │   ├── agricola_2003.csv
│   │   ├── ...
│   │   └── agricola_2025.csv
│   │
│   ├── raw_clima/
│   │   ├── clima_01_aguascalientes.csv
│   │   ├── ...
│   │   └── clima_32_zacatecas.csv
│   │
│   ├── interim/
│   │   └── municipios_coordenadas_inegi.csv
│   │
│   └── processed/
│       └── tidy.csv
│
├── notebooks/
│   ├── exploracion.ipynb
│   └── dataprocessing.ipynb
│
├── references/
│
├── reports/
│   └── figures/
│
├── requirements.txt
├── Makefile
└── README.md
```

---

# Adquisición de datos agrícolas

Los archivos agrícolas se descargan automáticamente para cada año.

Ejemplo:

```python
ANIO_INICIAL = 2003
ANIO_FINAL = 2025

ANIOS = list(
    range(
        ANIO_INICIAL,
        ANIO_FINAL + 1
    )
)
```

El proceso verifica si el archivo ya existe antes de descargarlo:

```python
if ruta.exists():
    print(f"[{anio}] Ya existe")
    continue
```

Esto permite ejecutar nuevamente el proceso sin descargar archivos que ya se encuentran disponibles localmente.

---

# Procesamiento

El procesamiento contempla:

1. Descarga de los archivos agrícolas 2003–2025.
2. Revisión y normalización del esquema histórico.
3. Conversión y validación de variables numéricas.
4. Obtención de geometrías municipales de INEGI.
5. Generación de coordenadas representativas por municipio.
6. Descarga de información climática histórica.
7. Agregación del clima diario a nivel municipio-año.
8. Integración de información agrícola y climática.
9. Creación de variables derivadas.
10. Aplicación de reglas de calidad.
11. Generación del conjunto final en `data/processed/tidy.csv`.

---

# Reglas de calidad

Durante el procesamiento se verifican, entre otros aspectos:

- duplicados
- valores faltantes
- consistencia de identificadores geográficos
- disponibilidad de coordenadas
- cobertura temporal
- consistencia de tipos numéricos
- número esperado de años por municipio
- compatibilidad de unidades de producción

Los valores faltantes de rendimiento y precio no son eliminados automáticamente, ya que parte de ellos corresponde a observaciones donde no existió superficie cosechada o producción registrada.

Asimismo, el volumen de producción no se agrega indiscriminadamente entre cultivos con unidades incompatibles.

---

# Variables climáticas y contexto ambiental

Además de las variables climáticas históricas, se utiliza una clasificación ambiental simplificada de los estados en categorías como:

- desértico
- bosque
- selva

Esta clasificación funciona únicamente como una variable contextual general y **no representa una medición directa del tipo de suelo**.

Las variables climáticas históricas obtenidas de ERA5 constituyen las mediciones temporales utilizadas para estudiar la variabilidad climática entre 2003 y 2025.

---

# Objetivo de modelado

Una etapa posterior del proyecto utilizará técnicas estadísticas y de aprendizaje automático para estudiar la relación entre las variables agrícolas y climáticas y los resultados de producción.

Una variable objetivo candidata es:

```text
TasaCosecha = Cosechada / Sembrada
```

Entre las posibles variables explicativas se encuentran:

- cultivo
- año
- ciclo productivo
- modalidad
- municipio
- estado
- clasificación ambiental
- temperatura
- precipitación
- evapotranspiración
- anomalías climáticas

La selección definitiva de variables y modelos se realizará después de completar el procesamiento, análisis exploratorio y evaluación de posibles problemas de fuga de información.

---

# Entorno de ejecución

Crear un entorno virtual e instalar las dependencias:

```bash
python -m venv .venv
```

En Windows:

```bash
.venv\Scripts\activate
```

Instalar dependencias:

```bash
pip install -r requirements.txt
```

Las principales librerías utilizadas son:

- pandas
- NumPy
- Matplotlib
- Requests
- GeoPandas
- scikit-learn
- joblib

---

# Estado actual del proyecto

Actualmente se cuenta con:

- datos agrícolas para 2003–2025
- auditoría del esquema histórico
- normalización de identificadores y variables
- geometrías municipales de INEGI
- coordenadas para los municipios agrícolas
- pipeline de descarga climática mediante Open-Meteo/ERA5
- almacenamiento incremental de información climática por estado
- preparación para la integración agrícola-climática

El siguiente paso es completar la información climática de los municipios agrícolas y construir el dataset integrado que será utilizado para análisis estadístico, visualización y modelado.