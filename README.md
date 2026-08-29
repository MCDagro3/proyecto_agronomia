# Análisis agrícola 2025

Proyecto de exploración y modelado de los datos de producción agrícola de
México publicados por la DGSIAP para 2025.

El proyecto permite:

- explorar la calidad y cobertura del conjunto de datos;
- generar gráficas y tablas resumen por cultivo y estado;
- entrenar un modelo de regresión usando el estado y el cultivo;
- estimar el porcentaje de superficie sembrada que llegará a cosecharse.

## Definición de la tasa de éxito

La variable objetivo se calcula como:

```text
Tasa de éxito (%) = Cosechada / Sembrada × 100
```

Por ejemplo, si se sembraron 1,000 hectáreas y se cosecharon 950, la tasa de
éxito es del 95 %.

Esta medida representa éxito de superficie, no rentabilidad económica,
rendimiento por hectárea ni probabilidad de éxito de un productor individual.

## Estructura

```text
proyecto_agronomia/
├── data/
│   ├── agricola_2025.csv
│   └── processed/
│       ├── datos_modelo_tasa_exito.csv
│       ├── modelo_tasa_exito.joblib
│       ├── resumen_cultivos_2025.csv
│       └── resumen_estados_2025.csv
├── figuras/
├── explorar_agricola_2025.py
├── modelo_tasa_exito.py
├── requirements.txt
└── README.md
```

Los archivos dentro de `data/processed` y `figuras` son generados por los
scripts.

## Requisitos

- Python 3.10 o posterior
- pip
- PowerShell, para seguir los ejemplos de Windows

Las principales bibliotecas son pandas, Matplotlib, Requests, scikit-learn y
joblib.

## Instalación en Windows

Abre PowerShell y entra en la carpeta del proyecto:

```powershell
cd B:\MCD2\JW\agro\proyecto_agronomia
```

Crea el entorno virtual dentro del proyecto:

```powershell
python -m venv .venv
```

Actívalo:

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea la activación, habilítala solamente para la sesión
actual:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Instala las dependencias:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Comprueba que se instaló todo correctamente:

```powershell
python -c "import joblib, pandas, sklearn; print('Dependencias instaladas')"
```

> Si VS Code selecciona `C:\msys64\ucrt64\bin\python.exe`, usa el comando
> **Python: Select Interpreter** y selecciona
> `.venv\Scripts\python.exe` dentro de este proyecto.

## Exploración de datos

El archivo `explorar_agricola_2025.py` utiliza por defecto:

```text
data/agricola_2025.csv
```

Ejecuta el análisis con:

```powershell
python explorar_agricola_2025.py
```

El script muestra:

- dimensiones y formato del CSV;
- valores nulos y duplicados;
- cobertura de estados, municipios, cultivos, ciclos y modalidades;
- estadísticas descriptivas de las variables numéricas.

También genera:

- `data/processed/resumen_cultivos_2025.csv`;
- `data/processed/resumen_estados_2025.csv`;
- cinco gráficas dentro de `figuras/`.

Para descargar nuevamente el archivo desde DGSIAP antes del análisis:

```powershell
python explorar_agricola_2025.py --descargar
```

Esta opción reemplaza el CSV indicado. También es posible proporcionar otra
ruta:

```powershell
python explorar_agricola_2025.py --csv ".\data\otro_archivo.csv"
```

## Entrenamiento del modelo

El script requiere un subcomando. Para procesar los datos y entrenar:

```powershell
python modelo_tasa_exito.py entrenar
```

Durante el procesamiento:

1. se cargan estado, cultivo, superficie sembrada y superficie cosechada;
2. se eliminan registros incompletos o inválidos;
3. se agregan las filas por combinación estado–cultivo;
4. se calcula la tasa de éxito;
5. se descartan tasas fuera del intervalo físico de 0 a 100 %;
6. se separa un 20 % de las combinaciones para evaluación;
7. se entrena un `RandomForestRegressor` con codificación categórica;
8. se reentrena con todos los datos y se guarda el modelo final.

Los artefactos resultantes son:

```text
data/processed/datos_modelo_tasa_exito.csv
data/processed/modelo_tasa_exito.joblib
```

Es posible indicar rutas diferentes:

```powershell
python modelo_tasa_exito.py entrenar `
  --csv ".\data\agricola_2025.csv" `
  --modelo ".\data\processed\modelo_tasa_exito.joblib"
```

## Realizar una predicción

Después de entrenar el modelo:

```powershell
python modelo_tasa_exito.py predecir `
  --estado "Aguascalientes" `
  --cultivo "Avena forrajera en verde"
```

Ejemplo de salida:

```text
Estado: Aguascalientes
Cultivo: Avena forrajera en verde
Tasa de éxito estimada: 99.89%
```

El programa acepta diferencias de mayúsculas y acentos. El estado y el cultivo
deben existir en los datos usados para entrenar; cuando no existen, se muestran
sugerencias cercanas.

Ejecutar el archivo sin `entrenar` o `predecir` produce un error de argumentos:

```powershell
# Incompleto
python modelo_tasa_exito.py

# Correcto
python modelo_tasa_exito.py entrenar
```

Para consultar la ayuda:

```powershell
python modelo_tasa_exito.py --help
python modelo_tasa_exito.py predecir --help
```

## Evaluación y limitaciones

En la ejecución inicial se obtuvieron aproximadamente estos resultados:

| Métrica | Resultado |
|---|---:|
| Combinaciones estado–cultivo | 2,227 |
| MAE | 8.09 puntos porcentuales |
| RMSE | 18.86 puntos porcentuales |
| R² | 0.050 |
| MAE de referencia | 9.17 puntos porcentuales |

El modelo mejora ligeramente la predicción basada en la media, pero el R² bajo
indica que estado y cultivo explican sólo una parte pequeña de la variación. Su
resultado debe interpretarse como una estimación inicial, no como una garantía.

Para mejorar el modelo se recomienda incorporar:

- municipio o región agrícola;
- modalidad de riego o temporal;
- ciclo productivo;
- superficie sembrada;
- condiciones climáticas;
- suelo y disponibilidad de agua;
- datos de varios años.

## Desactivar el entorno

Cuando termines:

```powershell
deactivate
```
