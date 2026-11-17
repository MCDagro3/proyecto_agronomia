# Auditoría de los aportes incorporados en `scripts/` y notebooks

## Objetivo

Revisar el material incorporado por el equipo, identificar lógica reutilizable y definir una ruta segura para retirar la carpeta paralela `scripts/` sin perder aportes útiles ni romper el flujo reproducible del proyecto.

## Conclusión ejecutiva

La carpeta `scripts/` no debe permanecer como una segunda arquitectura del proyecto. Crea `data_david/`, duplica la configuración Cookiecutter, introduce objetos pickle dependientes de clases locales y mezcla descarga, preparación y análisis.

Sin embargo, tres módulos contienen lógica que conviene migrar al paquete `proyecto_agronomia` antes de borrar la carpeta:

1. `avance.py`: cliente del avance de siembras y cosechas de DGSIAP.
2. `agroprograma.py`: cliente de intención de siembra y equivalencia de catálogos de cultivos.
3. `inegi_mapas.py`: búsqueda y descarga de series nacionales de uso del suelo y vegetación de INEGI.

Los demás archivos aportan principalmente ideas o reglas de limpieza, pero no conviene conservar su implementación actual.

## Revisión de `scripts/`

### `avance.py` — migrar

**Valor**

- Consulta el avance agrícola publicado por DGSIAP.
- Conserva filtros por año, mes, ciclo, modalidad, geografía y cultivo.
- Resuelve el protocolo antiguo `xajax` y la codificación `cp1252`.
- Puede servir para contrastar intención, avance y cierre de producción.

**Uso futuro**

- Seguimiento del año agrícola vigente.
- Comparación entre superficie programada, sembrada y cosechada.
- Storytelling sobre diferencias entre intención y resultado.

**Ajustes necesarios**

- Mover a `proyecto_agronomia/datasets/`.
- Usar URLs y rutas de `proyecto_agronomia.config`.
- Añadir pruebas de parsing con respuestas guardadas, sin depender de la red.
- Evitar depender de constantes ubicadas en `scripts.config`.

### `agroprograma.py` — migrar

**Valor**

- Consulta intención de siembra y cosecha.
- Obtiene catálogos de ciclos, modalidades, entidades, municipios, cultivos y variedades.
- Incluye una equivalencia entre los identificadores de cultivo de AgroPrograma y Avance Agrícola.

**Uso futuro**

- Comparar planes productivos con resultados observados.
- Agregar una señal de tradición o expectativa productiva.
- Evaluar si una recomendación del modelo coincide con decisiones actuales de productores.

**Ajustes necesarios**

- Migrar junto con el cliente de avance agrícola.
- Separar la homologación de nombres en una función probada.
- Guardar catálogos descargados con fecha de consulta.
- Tratar cambios del sitio como errores explícitos y verificables.

### `inegi_mapas.py` — migrar de forma opcional

**Valor**

- Localiza productos nacionales de uso del suelo y vegetación, series I–VII.
- Descarga archivos en flujo, usa reintentos y archivos temporales.
- Puede aportar restricciones territoriales para los escenarios de redistribución.

**Uso futuro**

- Estimar superficie agrícola disponible.
- Distinguir zonas agrícolas, forestales y otros usos del suelo.
- Evitar que la optimización asigne superficie fuera del espacio agrícola observado.

**Riesgos y ajustes**

- Utiliza una API interna de INEGI que puede cambiar sin aviso.
- La función modifica el diccionario de consulta recibido; debe trabajar con una copia.
- Debe guardar en la estructura oficial `data/raw` o `data/external`, no en `data_david`.
- Requiere validación del ZIP antes de reemplazar el archivo final.

### `mapbiomas.py` — conservar la idea, reescribir el código

**Valor conceptual**

MapBiomas podría ayudar a restringir la redistribución usando cobertura agrícola anual, perenne y mosaico agropecuario.

**Problemas**

- Ejecuta todo el procesamiento al importar el módulo.
- Depende de una carpeta y archivos preexistentes sin validación.
- Convierte cada píxel en una fila, lo que puede producir conjuntos extremadamente grandes.
- No agrega por municipio ni conserva de forma explícita CRS y resolución.
- Importa `rasterio`, pero esa dependencia no fue agregada al proyecto.

**Decisión**

No migrar el archivo. Si MapBiomas se incorpora, implementar un pipeline nuevo que haga estadística zonal por municipio.

### `Files.py` — eliminar

**Problemas**

- Duplica lectura, descarga y organización ya cubiertas por el paquete principal.
- Usa excepciones generales que ocultan errores.
- Puede referirse a una respuesta HTTP antes de que exista.
- La detección de nombre de archivo y codificación es frágil.
- Carga archivos completos para detectar codificación.
- Mezcla estado mutable, descarga, lectura y preparación.
- Es la base de objetos pickle no portables.

**Valor rescatable**

La idea de no repetir descargas y normalizar codificaciones ya está cubierta de manera más segura en los módulos actuales.

### `dgsiap.py` — eliminar después de rescatar reglas puntuales

**Problemas**

- Realiza una solicitud de red al importar el módulo.
- Depende de la estructura HTML actual del portal.
- No tiene caché, reintentos ni aislamiento de parsing.

**Valor rescatable**

- Descubrimiento de enlaces históricos y diccionarios.
- Metadatos de fecha, rango y tamaño.

La implementación debería reemplazarse por una función explícita dentro de `datasets/agricultura.py` si vuelve a necesitarse.

### `config.py` y `__init__.py` — eliminar

**Problemas**

- Crean directorios como efecto de importación.
- Definen una segunda raíz de datos: `data_david/`.
- Conservan referencias obsoletas a Open-Meteo.
- Duplican fuentes, rutas y configuración ya existentes.
- `__init__.py` intenta crear una jerarquía distinta de la que crea `config.py`.

## Revisión de notebooks

### `agroprod_0.ipynb`

Explora la descarga del diccionario y archivos históricos de DGSIAP. Su aporte principal es el descubrimiento de fuentes. Depende completamente de `scripts/` y guarda objetos pickle; no debe formar parte del pipeline final.

### `agroprod_1.ipynb`

Analiza cambios históricos en columnas y reglas del diccionario. Aportes rescatables:

- Detección de variaciones de esquema entre años.
- Validación de categorías, tipos y rangos documentados.
- Identificación del cambio entre `Precio` y `Preciomediorural`.

La implementación es exploratoria, repetitiva y dependiente de objetos pickle. Las reglas útiles deben trasladarse a funciones y pruebas.

### `agroprod_2.ipynb`

Contiene la limpieza más útil del grupo:

- Homologación del nombre del cultivo cuando la unidad aparece entre paréntesis.
- Tratamiento de `#¡NUM!` en rendimiento.
- Eliminación de separadores de miles.
- Corrección de tipos históricos.

Estas reglas deben compararse con `features.py` y migrarse de forma explícita. El notebook no debe ser una dependencia de integración.

### `agroprod_3.ipynb`

Aporta ideas de storytelling:

- Tasa de superficie cosechada respecto a sembrada.
- Comparación de estados líderes por cultivo.
- Diferencias entre superficie sembrada, cosechada y valor de producción.

La tasa ya existe como `TasaCosecha` en `features.py`. Las demás comparaciones pueden incorporarse al análisis exploratorio, pero el código contiene repeticiones y lógica difícil de validar.

### `preparacion_agricola.ipynb`

Mezcla dos pipelines:

- Primera parte: copia del flujo de `agroprod_1`, dependiente de `scripts/` y variables no definidas.
- Segunda parte: funciones del paquete actual (`cargar_archivo_agricola`, `construir_historico_agricola`, `generar_features_agricolas`).

Contiene una celda incompleta (`datadict =`) y referencias a objetos no creados en la propia notebook. No es reproducible de principio a fin. Conviene reconstruirla usando solamente el paquete principal.

## Archivos `preload/*.pkl`

Los archivos pickle guardan instancias de clases de `scripts.Files`. No son datasets autocontenidos:

- Requieren conservar la misma ruta de importación y clases.
- Pueden contener rutas absolutas de la máquina que los generó.
- No deben cargarse si su procedencia no es plenamente confiable, porque pickle puede ejecutar código durante la deserialización.
- Falta `DGSIAP_EDA.pkl`, aunque aparece en la configuración.

**Decisión:** retirar los pickle junto con el pipeline antiguo. Los productos intermedios reproducibles deben guardarse como CSV o Parquet con metadatos.

## Referencias nuevas

- `references/Codebook_ProdAgro_mun.xlsx`
- `references/Variables_ProdAgro_mun.xlsx`

Conviene conservarlas temporalmente y compararlas con `diccionario_datos_agricultura_dgsiap.xlsx`. Pueden documentar reglas de tipos, rangos y variables. Si son duplicados, se elegirá una sola fuente canónica y se registrará su origen.

## Regresión detectada en la integración

`notebooks/integracion_agricultura_clima.ipynb` fue modificado para leer:

`data_david/process/DGSIAP/ProdAgro*.csv`

Esto rompe la reproducibilidad porque:

- `data_david/` está ignorado por Git.
- La carpeta no se genera mediante el pipeline oficial.
- La integración pasa a depender de `agroprod_2.ipynb` y de los pickle.
- Cambia el esquema agrícola y elimina una columna respecto al flujo anterior.
- El mensaje de error todavía apunta a otra ruta, lo que dificulta el diagnóstico.

La integración debe volver a consumir `data/raw/agricultura/agricola_*.csv` mediante funciones normalizadas del paquete, o un único producto procesado generado de manera reproducible.

## Dependencias

- `cchardet`: sólo respalda `Files.py`; retirar al eliminar ese módulo.
- `beautifulsoup4`/`bs4`, `lxml` y `yarl`: conservar únicamente si se migran los clientes DGSIAP/INEGI.
- `openpyxl`: útil para diccionarios Excel.
- `rasterio`: necesario sólo si se implementa correctamente un pipeline MapBiomas; actualmente no está declarado.

## Plan de limpieza recomendado

1. Restaurar la fuente agrícola reproducible de la notebook de integración.
2. Incorporar en `features.py` las reglas útiles de normalización histórica y añadir pruebas.
3. Migrar `avance.py` y `agroprograma.py` a `proyecto_agronomia/datasets/` si se usarán en el storytelling.
4. Decidir si la descarga de uso del suelo de INEGI entra en el alcance inmediato; migrar `inegi_mapas.py` sólo si la respuesta es afirmativa.
5. Reconstruir o retirar `preparacion_agricola.ipynb`.
6. Archivar o eliminar `agroprod_0.ipynb`–`agroprod_3.ipynb` después de extraer sus reglas y conclusiones.
7. Eliminar `scripts/`, `preload/*.pkl` y `DGSIAP_DIR`.
8. Retirar dependencias que queden sin uso y actualizar `uv.lock`.
9. Ejecutar nuevamente descarga/preparación, integración y validaciones de cobertura.
