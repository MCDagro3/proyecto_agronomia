# Preguntas de investigación

## Propósito

Identificar patrones entre la producción agrícola, el clima y las características del suelo de los municipios de México durante 2003–2025. El análisis busca describir asociaciones y generar hipótesis; una asociación observada no debe interpretarse automáticamente como causalidad.

## Unidad de análisis

La unidad principal será una observación de:

`municipio + año + ciclo productivo + cultivo`

La clave geográfica será `cvegeo`. Las características edafológicas son relativamente estables en el periodo y se incorporarán como atributos municipales. El clima variará por año, mes y ventana del ciclo agrícola.

## Datos disponibles

### Agricultura

- Fuente: datos abiertos de la Secretaría de Agricultura.
- Periodo: 2003–2025.
- Variables principales: cultivo, ciclo productivo, superficie sembrada, superficie cosechada, producción y rendimiento.
- Nivel geográfico: municipio.

### Clima

- Fuente: NASA POWER.
- Archivo mensual: `data/processed/clima_nasa/clima_municipal_mensual_2002_2025.csv`.
- Variables principales: temperatura media mensual y precipitación mensual.
- El año 2002 se conserva para construir el ciclo Otoño–Invierno de 2003.
- Las ventanas climáticas se alinean con Otoño–Invierno, Primavera–Verano y Perennes.

### Edafología

- Fuente: INEGI, Conjunto Nacional de Información Edafológica Serie III, escala 1:250 000.
- Capa principal: polígonos de unidades edafológicas.
- Variables municipales derivadas: grupo de suelo dominante, porcentaje de superficie que ocupa, número de grupos presentes, textura dominante y fases física y química dominantes.
- La atribución municipal se realizará por intersección espacial y superficie, no mediante centroides.

## Dataset integrado

El archivo de partida es:

`data/processed/agricultura_clima_2003_2025.csv`

La integración edafológica generará:

`data/processed/agricultura_clima_edafologia_2003_2025.csv`

Variables analíticas esperadas:

- Identificación: `cvegeo`, estado, municipio, año, ciclo y cultivo.
- Respuesta agrícola: superficie sembrada, cosechada, producción y rendimiento.
- Clima: temperatura y precipitación mensual, temperatura media del ciclo y precipitación acumulada del ciclo.
- Suelo: grupo dominante, nombre WRB, porcentaje dominante, diversidad de grupos, textura y fases dominantes.

## Pregunta principal

¿Cómo se relacionan la temperatura, la precipitación y las características del suelo con la distribución y el desempeño de los cultivos en los municipios de México entre 2003 y 2025?

## Preguntas específicas

1. ¿Qué cultivos predominan en cada combinación de grupo de suelo, textura y régimen climático?
2. ¿Qué tipos de suelo presentan mayores rendimientos para cada cultivo?
3. ¿Cómo cambia el rendimiento de un cultivo cuando la temperatura o la precipitación se alejan de su comportamiento histórico municipal?
4. ¿Qué meses o etapas del ciclo agrícola tienen mayor asociación con el rendimiento?
5. ¿La relación entre precipitación y rendimiento cambia según el grupo o la textura del suelo?
6. ¿Qué combinaciones de suelo y clima mantienen rendimientos más estables durante años cálidos o secos?
7. ¿Existen municipios con condiciones ambientales semejantes pero resultados agrícolas diferentes?
8. ¿Cómo ha cambiado espacialmente el cultivo predominante entre 2003 y 2025?
9. ¿Los municipios con mayor diversidad edafológica presentan también una mayor diversidad de cultivos?
10. ¿Qué cultivos aparecen en zonas que podrían considerarse climática o edafológicamente marginales?

## Indicadores iniciales

- Rendimiento por hectárea y su anomalía respecto a la media histórica del municipio y cultivo.
- Precipitación acumulada y temperatura media durante el ciclo productivo.
- Anomalías climáticas respecto al promedio municipal de 2003–2025.
- Variabilidad interanual del rendimiento.
- Porcentaje municipal del suelo dominante.
- Número de grupos de suelo presentes en el municipio.
- Diversidad de cultivos por municipio y año.
- Superficie cosechada perdida: diferencia entre superficie sembrada y cosechada.

## Precauciones de interpretación

- Las unidades edafológicas tienen escala 1:250 000 y describen áreas, no parcelas individuales.
- El clima de NASA POWER representa celdas de una malla y no microclimas locales.
- Los registros agrícolas pueden cambiar en cobertura y calidad entre años.
- Los ciclos agrícolas no representan fechas exactas de siembra y cosecha para todos los cultivos.
- Conviene controlar por municipio, año, cultivo, ciclo y superficie antes de comparar rendimientos.
- Los resultados exploratorios mostrarán asociaciones; evaluar causalidad requerirá un diseño estadístico adicional.
