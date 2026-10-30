# Diccionario de datos edafológicos

## Fuente y alcance

Este documento resume los campos disponibles en el **Conjunto Nacional de
Información Edafológica, escala 1:250 000, Serie III**, publicado por el
Instituto Nacional de Estadística y Geografía (INEGI). La clasificación se
basa en la Base Referencial Mundial del Recurso Suelo (WRB 2014).

- Producto: Conjunto Nacional de Información Edafológica, Serie III.
- Escala: 1:250 000.
- Cobertura: nacional.
- Información levantada principalmente durante 2013-2020.
- Uso temporal en el proyecto: característica territorial estática para los
  registros agrícolas de 2003-2025.
- Diccionario oficial local:
  [`diccionario_datos_edafologicos_250k_v4.pdf`](diccionario_datos_edafologicos_250k_v4.pdf).
- Fuente oficial: [Diccionario de datos edafológicos de INEGI](https://www.inegi.org.mx/contenidos/productos/prod_serv/contenidos/espanol/bvinegi/productos/nueva_estruc/702825092023.pdf).

## Capas utilizadas

### Unidad de suelo (`*_area.shp`)

Capa de polígonos que representa unidades individuales o asociaciones de
grupos de suelo. Es la capa principal para construir características por
municipio mediante intersección espacial y ponderación por superficie.

| Campo | Tipo esperado | Descripción | Uso municipal recomendado |
|---|---|---|---|
| `OBJECTID` | entero | Identificador interno del objeto espacial. | Control técnico; no usar como clave temática. |
| `Clave_wrb` | texto | Clave completa de la asociación: grupos, calificadores, textura y, cuando corresponde, limitante superficial. | Conservar como clasificación detallada; calcular la clave predominante por superficie. |
| `Grupo1` | texto | Grupo de suelo dominante; ocupa 60% o más de la unidad cartográfica. | Grupo dominante y porcentaje del municipio donde aparece como dominante. |
| `Califp_g1` | texto | Calificador primario del suelo dominante. | Calificador predominante por superficie. |
| `Califs_g1` | texto | Calificador secundario del suelo dominante. | Calificador secundario predominante por superficie. |
| `Grupo2` | texto | Suelo secundario; se estima que ocupa entre 20% y 40% de la unidad. | Indicador de presencia; no tratar como porcentaje exacto. |
| `Califp_g2` | texto | Calificador primario del suelo secundario. | Análisis complementario de asociaciones. |
| `Califs_g2` | texto | Calificador secundario del suelo secundario. | Análisis complementario de asociaciones. |
| `Grupo3` | texto | Suelo terciario; se estima que ocupa como máximo 20% de la unidad. | Indicador de presencia; no tratar como porcentaje exacto. |
| `Califp_g3` | texto | Calificador primario del suelo terciario. | Análisis complementario de asociaciones. |
| `Clase_tex` | texto | Clase textural de los primeros 30 cm del suelo dominante. | Textura predominante y porcentajes de superficie por clase. |
| `Lmte_sup` | texto | Limitante física superficial del suelo dominante. | Porcentaje municipal pedregoso, gravoso o sin limitante. |
| `Fase_fis_u` | texto | Material duro, roca continua o cementación presente entre 0 y 100 cm. | Porcentajes municipales por fase física. |
| `Fase_qui_u` | texto | Salinidad, sodicidad o saturación de sodio más magnesio. | Porcentajes municipales por fase química. |
| `Shape_Leng` | real | Longitud almacenada por el producto geográfico. | No usar como característica del suelo. |
| `Shape_Area` | real | Superficie original del polígono. | No usar después de recortar; recalcular el área de cada intersección. |
| `geometry` | geometría | Polígono de la unidad de suelo. | Intersección espacial con límites municipales. |

## Dominios de la unidad de suelo

### Grupos de suelo WRB

| Código | Nombre | Código | Nombre |
|---|---|---|---|
| `AC` | Acrisol | `AL` | Alisol |
| `AN` | Andosol | `AT` | Anthrosol |
| `AR` | Arenosol | `CL` | Calcisol |
| `CM` | Cambisol | `CH` | Chernozem |
| `CR` | Cryosol | `DU` | Durisol |
| `FR` | Ferralsol | `FL` | Fluvisol |
| `GL` | Gleysol | `GY` | Gypsisol |
| `HS` | Histosol | `KS` | Kastanozem |
| `LP` | Leptosol | `LX` | Lixisol |
| `LV` | Luvisol | `NT` | Nitisol |
| `PH` | Phaeozem | `PL` | Planosol |
| `PT` | Plinthosol | `PZ` | Podzol |
| `RG` | Regosol | `RT` | Retisol |
| `SC` | Solonchak | `SN` | Solonetz |
| `ST` | Stagnosol | `TC` | Technosol |
| `UM` | Umbrisol | `VR` | Vertisol |

Los valores `N`, `N/A` y `N/D` no representan grupos de suelo: indican,
según el atributo, ninguno, no aplicable o no disponible.

### Textura (`Clase_tex`)

| Código | Categoría | Interpretación |
|---|---|---|
| `1` | Gruesa | Textura gruesa de los primeros 30 cm del suelo dominante. |
| `2` | Media | Textura media de los primeros 30 cm del suelo dominante. |
| `3` | Fina | Textura fina de los primeros 30 cm del suelo dominante. |
| `N/D`, `N/A` | Sin clasificación utilizable | Dato no disponible o no aplicable. |

### Limitante física superficial (`Lmte_sup`)

Indica fragmentos de roca u otros minerales en más del 30% del área.

| Código | Categoría |
|---|---|
| `P` | Pedregosa |
| `G` | Gravosa |
| `N` | Ninguna |
| `N/A` | No aplicable, por ejemplo en ciertas unidades Technosol |

Antes del procesamiento se deben normalizar mayúsculas y minúsculas; la capa
puede contener variantes como `p`.

### Fase física (`Fase_fis_u`)

| Código | Categoría |
|---|---|
| `li` | Lítico |
| `lep` | Epiléptico |
| `len` | Endoléptico |
| `pdp` | Epipetrodúrico |
| `pdn` | Endopetrodúrico |
| `pcp` | Epipetrocálcico |
| `pcn` | Endopetrocálcico |
| `pgp` | Epipetrogípsico |
| `pgn` | Endopetrogípsico |
| `N` | Ninguna |
| `N/A` | No aplicable |

### Fase química (`Fase_qui_u`)

| Código | Categoría |
|---|---|
| `qz` | Protosálica |
| `sz` | Sálica |
| `jz` | Hipersálica |
| `qs` | Protosódica |
| `so` | Sódica |
| `N` | Ninguna |
| `N/A` | No aplicable |

### Calificadores

Los campos `Califp_*` y `Califs_*` contienen códigos WRB que describen
cualidades del grupo de suelo. El catálogo completo es extenso y está en el
anexo C del diccionario oficial. Deben conservarse como variables categóricas
y traducirse mediante una tabla de consulta cuando se utilicen en resultados
destinados a lectura humana.

## Perfil de suelo (`*_pto.shp`)

La capa puntual representa sitios de muestreo. Cada sitio puede tener varios
horizontes, por lo que una fila no equivale a un municipio ni necesariamente
a un perfil completo.

### Identificación y profundidad

| Campo | Descripción |
|---|---|
| `Id_Sitio` | Identificador del sitio o perfil. |
| `Id_Hte` | Identificador único del horizonte o capa. |
| `Numero_Hte` | Número del horizonte. |
| `Limite_sup` | Profundidad superior del horizonte, en centímetros. |
| `Limite_inf` | Profundidad inferior del horizonte, en centímetros. |
| `Coord_x`, `Coord_y` | Coordenadas del sitio. |
| `Fecha` | Fecha del levantamiento. |
| `geometry` | Punto de ubicación del perfil. |

### Clasificación y contexto del sitio

| Campos | Contenido |
|---|---|
| `Clave_wrb`, `Gpo_suelo`, `Calif_prim`, `Calif_sec` | Clasificación WRB del perfil. |
| `Fase_fisic`, `Fase_quim` | Fases física y química observadas. |
| `Altitud`, `Precip`, `Temp`, `Clima` | Contexto ambiental registrado para el perfil. |
| `Prov_fisio`, `Subpro_fis`, `Topoforma` | Contexto fisiográfico. |
| `Roca_subya`, `Edad_geol`, `Edad_geofo` | Material y contexto geológico. |
| `Relieve`, `Modo_forma` | Relieve y modo de formación. |
| `Cober_tier` | Cobertura de la tierra. |
| `Pos_pend`, `Forma_pend`, `Grad_pend`, `Compl_pend`, `Orien_pend`, `Long_pend` | Características de la pendiente. |
| `Pedreg_sup`, `Afloramien`, `Escurr_sup`, `Infiltra`, `Superf_sue` | Condiciones superficiales e hidrológicas. |
| `Tipo_eros`, `Forma_eros`, `Grado_eros` | Erosión observada. |
| `Influe_hum`, `Fact_nociv` | Influencia humana y factores nocivos. |

### Propiedades del horizonte y análisis de laboratorio

| Campo | Descripción o unidad |
|---|---|
| `R`, `L`, `A` | Porcentajes de arcilla, limo y arena, respectivamente. |
| `Clase_text` | Clase textural determinada en laboratorio. |
| `CE` | Conductividad eléctrica. |
| `pH` | Potencial de hidrógeno. |
| `CO` | Carbono orgánico. |
| `CIC` | Capacidad de intercambio catiónico. |
| `SB` | Saturación con bases, porcentaje. |
| `SNa` | Saturación de sodio, porcentaje. |
| `K` | Potasio intercambiable, cmol/kg. |
| `Ca` | Calcio intercambiable, cmol/kg. |
| `Na` | Sodio intercambiable, cmol/kg. |
| `Mg` | Magnesio intercambiable, cmol/kg. |
| `P2O5` | Fósforo disponible, mg/kg. |
| `CaCO3` | Carbonatos de calcio, porcentaje. |
| `CaSO4` | Sulfatos de calcio, porcentaje. |
| `DA` | Densidad aparente, g/cm³. |
| `Na_Mg` | Relación o proporción sodio más magnesio. |

Otros campos describen estructura, humedad, color, consistencia, adhesividad,
plasticidad, grava, piedra, concreciones, nódulos, manchas, raíces,
cementación y horizontes de diagnóstico. Su definición detallada debe
consultarse en el diccionario oficial antes de incorporarlos a un modelo.

## Reglas para generar características municipales

1. Usar la capa de polígonos como fuente principal.
2. Reproyectar municipios y suelos al mismo sistema de coordenadas métrico.
3. Intersectar ambas capas y recalcular el área de cada fragmento; no reutilizar
   `Shape_Area` después del recorte.
4. Calcular `porcentaje = area_interseccion / area_municipio * 100`.
5. Agregar por `cvegeo`, variable y categoría.
6. Conservar una tabla larga de composición y otra tabla compacta con los
   atributos predominantes.
7. Reportar `cobertura_edafologica_pct` para distinguir ausencia real de una
   categoría de falta de cobertura cartográfica.
8. No interpretar el área donde `Grupo1` es dominante como proporción exacta
   de ese grupo en campo: es el área municipal cubierta por unidades donde ese
   grupo ocupa al menos 60%.
9. No promediar directamente los perfiles puntuales por municipio. Para usar
   pH, carbono orgánico u otras mediciones se debe seleccionar una profundidad
   comparable, evaluar el número y distribución de sitios y aplicar una
   metodología espacial con incertidumbre.

## Estructura sugerida de salidas

### Composición larga

```text
cvegeo | variable | categoria | area_km2 | porcentaje
```

### Características municipales

```text
cvegeo
suelo_dominante
suelo_dominante_pct
textura_dominante
textura_gruesa_pct
textura_media_pct
textura_fina_pct
pedregoso_pct
gravoso_pct
sin_limitante_superficial_pct
fase_fisica_pct
fase_quimica_pct
salino_pct
sodico_pct
numero_unidades_suelo
diversidad_suelos
cobertura_edafologica_pct
```

