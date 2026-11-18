# Producción Agrícola en México

México, según el DGSIAP, es el décimo productor agrícola a nivel mundial. Sin embargo, resulta curioso como paises como paises como Indonesia, Pakistan y Nigeria, siendo más pequeños, producen mayor cantidad. Considerando que Nigeria produce $30\%$ más que México siendo $50\%$ más pequeño motiva investigar si México tiene posibilidad a aumentar.

## Objetivo. 

A partir de nuestra primera. Nuestro proyecto realizara un analisis a la distribución de los cultivos del pais con la intención de explorar nuevas propuestas con la intención de aumentar la producción agricola nacional. 

## Datos.

Nuestro analisis explorará la distribución de los cultivos a nivel municipio. Revisando los 3 bloques principales en la agricultura. 

* El clima.
* El suelo.
* La historia

Indagando como estos 3 bloques actuan sobre la distribución actual y explorar escenarios de mejora.

### La historia.

No se parté de cero. México ha sembrado desde hace muchos años. Por lo tanto, nuestro analisis se centrará en producción agricola pasada. El pasado agricola, y en general la información agricola del pais, es gestionada por el Servicio de Información Agroalimentaria y Pecuaria o SIAP. En particular, la producción agricola historica se encuentra en el portal de Datos Abiertos de la Dirección General del SIAP. 

### El Clima.

Partiendo del supuesto empirico que variables metereologicas como la lluvia, la temperatura media definen el cultivo plantado en cada municipio. Actualmente existen distintas fuentes para consultar la información meteorologica de una región. Para este analisis nos decidimos por utilizar la información meteoreologica proporcionada por la NASA mediante su portal NASA POWER.

### El Suelo.

Las variables principales al considerar el suelo como un elemento de nuestro analisis es su composición y su uso. La composición, al igual que el clima puede dar señales de cual es el cultivo más adecuado en una región determinada y su uso. Variable "trivial" que puede darnos información con respecto a los limites teóricos de producción agricola. 

Para este ultimo apartado utilizamos 3 fuentes. Para la composición utilizamos los mapas de edafologia que proporcioa INEGI que muestran la distribución de los tipos de suelo en México. Para el Uso de Suelo se utilizaron dos fuentes complementarias. Por un lado se utilizaron las Series de la Carta de Uso de Suelo y Vegetación de INEGI y el proyecto MAPBIOMAS México. Ambos nos presentan como se distribuye cada tipo de agricultura en el pais. 

## Ingesta de Datos.

Para este proyecto se priorizÓ la descarga automatica de los conjuntos de datos. Permitiendo la reproducibilidad del analisis. A continuación presentamos las técnicas empleadas y los desafios.

### API
El conjunto de datos climaticos proporcionados por el portal de NASA POWER fue obtenido meidante el uso de su API, denominada como POWER Daily API, en particular la que nos permitió extraer los datos metereologicos usando las coordenadas geográficas.


### WebScraping.
Por desgracia, no todos los datos pudieron obtenerse mediante el uso de APIs. Entonces, la producción agricola historica y los mapas proporcionados por el INEGI fueron descargados de forma programatica mediante una exploración previa del Portal de Datos Abiertos del DGSIAP y el Portal de Mapas de INEGI. Obteniendo los enlaces que dirigen a los archivos de nuestro interés.


### Descarga Manual

Por desgracia, para el caso de MAPBIOMAS no se ha encontrado una técnica viable para la descarga programatica. Teniendo que haber sido descargados de forma manual con ayuda de las herramientas proporcionadas por MAPBIOMAS.


## Retos 

Durante la descarga de los datos surgen situaciones que deben evaluarse y resolverse antes de continuar con el analisis. 

### Archivos ilegibles.

Esto ocurrió con los archivos de producción agrícola. El conjunto de datos crudos dependia de 2 partes. El diccionario de datos, que vino en formato .xlsx y los datos que venían en un conjunto de 23 archivos (Producción Anual desde 2003 hasta 2025). Estos ultimos no eran legibles por pandas, esto debido que pandas no lograba identificar la codificación utilizada al construirlo. En el proyecto, con uso de librerias adicionales (cchardet) identificamos la codificación más probable y la utilizamos para que pandas lea los .csv. 

### Archivos muy grandes.

El mapa de México en la sección de Mapas que almacena los municipios pesa más de 2 GB. Descargar esto para realizar nuestro analisis es inviable. Entonces, en la misma plataforma descargamos los mapas municipales de cada estado por separado.

### Formatos "Desconocidos".

Al descargar los mapas de MAPBIOMAS notamos que estos no venian en formato .shp (como los mapas de INEGI), sino que venian con formato .tiff. Esto implico la exploración de librerias adicionales como rasterio para poder leer y procesar más adelante. 

### Cambio de Fuente.

Al comienzo del proyecto se decidió usar la API de OPENMETEO para la obtención de los datos climaticos. Sin embargo, la extracción de los datos era inviable debido a las limitaciones de la API. Esto nos llevo a explorar otras opciones como: 

* Conjuntos de Datos Estáticos: Bases de Datos como ClimateHighRes.
* Datos generados por estaciones metereologicas de CONAGUA.
* Otras APIs como WeatherAPI y NASA POWER.