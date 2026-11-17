# Preguntas de investigación

## Historia que queremos contar

México produce una gran diversidad de cultivos en municipios con climas y suelos distintos. Parte de esa distribución puede explicarse por condiciones ambientales favorables, pero también por tradición productiva, infraestructura, acceso al riego, conocimiento local, mercado y políticas agrícolas.

Este proyecto busca evaluar si la distribución agrícola observada aprovecha adecuadamente las condiciones de cada municipio y localizar oportunidades para mejorar la producción. La pregunta no es únicamente **dónde se produce más**, sino:

> ¿Los cultivos se producen donde tienen mejores condiciones y desempeño, o existen municipios donde otra distribución podría aprovechar mejor el clima y el suelo?

El resultado esperado será una comparación entre la distribución observada y una distribución potencial estimada mediante modelos. La propuesta debe interpretarse como apoyo para generar escenarios y preguntas, no como una instrucción automática para sustituir cultivos.

## Objetivo general

Estimar el potencial productivo de diferentes cultivos en los municipios de México a partir de su historia agrícola, clima, suelo y modalidad de producción, para identificar:

1. Municipios que producen eficientemente cultivos asociados con su tradición agrícola.
2. Municipios cuyo desempeño parece estar favorecido por sus condiciones climáticas y edafológicas.
3. Cultivos con desempeño inferior al esperado dadas las condiciones del municipio.
4. Combinaciones municipio–cultivo con potencial productivo que actualmente tienen poca o ninguna presencia.
5. Escenarios de redistribución agrícola que podrían aumentar la producción esperada sin ignorar restricciones agronómicas y sociales.

## Pregunta principal

¿Cómo podría ajustarse la distribución municipal de los cultivos para mejorar la producción esperada, aprovechando el clima y el suelo de cada municipio, sin perder de vista la experiencia productiva acumulada y las restricciones de cada territorio?

## Preguntas de investigación

### Distribución y especialización observadas

1. ¿Qué cultivos caracterizan históricamente a cada municipio y región?
2. ¿Qué municipios muestran una especialización agrícola estable durante 2003–2025?
3. ¿Qué cultivos han ganado o perdido superficie cosechada y en qué regiones ocurrió el cambio?
4. ¿La diversidad de cultivos está relacionada con la diversidad de suelos y climas del municipio?

### Desempeño productivo

5. ¿Qué municipios obtienen rendimientos consistentemente superiores para cada cultivo?
6. ¿Qué parte de las diferencias de rendimiento se asocia con temperatura, precipitación, suelo, modalidad de producción y tendencia temporal?
7. ¿Qué combinaciones de cultivo, suelo y clima muestran rendimientos altos y estables?
8. ¿Qué municipios mantienen buenos resultados durante periodos secos, cálidos o simultáneamente secos y cálidos?
9. ¿Existen municipios con condiciones ambientales semejantes pero rendimientos muy diferentes?

### Tradición, condiciones ambientales y prácticas productivas

10. ¿Los cultivos tradicionales de un municipio presentan un desempeño superior al esperado por sus condiciones ambientales?
11. ¿Existen cultivos con buenos resultados principalmente en municipios con una larga historia de producción, aun cuando sus condiciones ambientales no parecen óptimas?
12. ¿La modalidad de riego o temporal modifica la relación entre clima, suelo y rendimiento?
13. ¿Qué municipios presentan un rendimiento superior al estimado por el modelo y podrían reflejar conocimiento local, infraestructura o prácticas productivas no observadas?

Estas preguntas permiten detectar señales compatibles con tradición o buen manejo, pero los datos disponibles no contienen mediciones directas de tecnología, fertilización, semillas, maquinaria, capacitación o infraestructura. Por ello, **no se atribuirá causalmente** un rendimiento alto a “mejores técnicas”; se describirá como desempeño no explicado que requiere investigación adicional.

### Potencial y redistribución

14. ¿En qué municipios podría obtenerse un rendimiento competitivo para un cultivo que actualmente tiene poca presencia?
15. ¿Qué cultivos parecen estar ubicados en municipios con condiciones menos favorables que otras alternativas disponibles?
16. ¿Cuánta producción adicional se estimaría al reasignar una parte de la superficie entre cultivos compatibles?
17. ¿Qué recomendaciones permanecen estables ante distintos años climáticos y cuáles dependen de condiciones excepcionales?
18. ¿Qué municipios o cultivos tienen demasiada incertidumbre para emitir una recomendación?

## Hipótesis de trabajo

- **H1. Especialización eficiente:** algunos municipios tienen rendimientos altos y estables porque combinan condiciones ambientales favorables con experiencia productiva acumulada.
- **H2. Ventaja ambiental desaprovechada:** existen municipios con clima y suelo favorables para ciertos cultivos cuya superficie actual es pequeña.
- **H3. Dependencia de manejo:** municipios con condiciones ambientales similares pueden presentar desempeños distintos por factores productivos no observados.
- **H4. Sensibilidad diferenciada:** la respuesta a temperatura y precipitación cambia según cultivo, suelo, ciclo y modalidad de producción.
- **H5. Redistribución parcial:** una reasignación limitada de superficie puede elevar la producción esperada más que una sustitución amplia de cultivos.
- **H6. Incertidumbre espacial:** las predicciones son menos confiables en combinaciones municipio–cultivo sin antecedentes o con condiciones fuera del rango observado.

## Datos disponibles

### Agricultura

- Fuente: datos abiertos de la Secretaría de Agricultura.
- Periodo: 2003–2025.
- Nivel: municipio, año, cultivo, ciclo y modalidad.
- Variables principales: superficie sembrada, cosechada y siniestrada; volumen de producción; rendimiento; precio y valor de producción.
- Utilidad: describir especialización, desempeño, estabilidad y evolución productiva.

### Clima

- Fuente: NASA POWER.
- Periodo mensual disponible: 2002–2025.
- Variables principales: temperatura media y precipitación acumulada.
- El año 2002 permite construir el ciclo Otoño–Invierno de 2003.
- Ventanas utilizadas:
  - Otoño–Invierno: octubre–diciembre del año anterior y enero–marzo del año agrícola.
  - Primavera–Verano: abril–septiembre.
  - Perennes: enero–diciembre.
- Utilidad: caracterizar condiciones del ciclo, anomalías, extremos y estabilidad climática.

### Edafología

- Fuente: INEGI, Serie III, escala 1:250 000.
- Variables municipales: grupo de suelo dominante, porcentaje de cobertura, diversidad edafológica, textura y fases física y química dominantes.
- Método: intersección espacial entre unidades edafológicas y municipios.
- Utilidad: representar aptitud y restricciones edafológicas generales.

### Variables que no están disponibles

El proyecto no dispone todavía de información completa sobre:

- Disponibilidad y costo del agua.
- Fertilización, semillas, maquinaria y manejo de plagas.
- Infraestructura, acceso a crédito y capacitación.
- Costos de producción y transporte.
- Demanda, contratos, cadenas de suministro y volatilidad de precios.
- Pendiente, altitud detallada y riesgos locales.
- Rotación de cultivos y decisiones a nivel parcela.
- Tenencia de la tierra y preferencias de los productores.

Estas ausencias limitan las explicaciones causales y la factibilidad de una redistribución. Las recomendaciones iniciales serán escenarios de potencial biofísico y productivo, no planes definitivos de reconversión.

## Unidad de análisis

La unidad principal será:

`municipio + año + ciclo productivo + modalidad + cultivo`

La clave geográfica será `cvegeo`. Antes de modelar, los registros se consolidarán para evitar múltiples observaciones de una misma combinación y el rendimiento se calculará de forma consistente como:

`volumen de producción / superficie cosechada`

Las comparaciones entre cultivos respetarán su unidad de medida. No se compararán directamente valores de rendimiento que representen productos o unidades incompatibles.

## Resultado que debe predecir el modelo

El modelo principal estimará el rendimiento esperado de un cultivo bajo una combinación de:

- Municipio.
- Año o escenario climático.
- Ciclo productivo.
- Modalidad de producción.
- Características del suelo.
- Historia productiva disponible.

La producción potencial se calculará después como:

`rendimiento esperado × superficie asignada`

El modelo deberá devolver tanto una predicción como una medida de incertidumbre. No se recomendarán combinaciones con poca evidencia o extrapolación ambiental excesiva.

## Estrategia analítica propuesta

### 1. Línea base descriptiva

- Identificar cultivos predominantes y especialización municipal.
- Calcular rendimientos históricos, estabilidad y tendencias.
- Comparar desempeño entre suelos, climas, ciclos y modalidades.
- Detectar años secos, cálidos y con alta siniestralidad.

### 2. Modelo de rendimiento

Entrenar modelos por cultivo o por grupos de cultivos comparables. Las variables predictoras podrán incluir clima mensual alineado con el ciclo, suelo, modalidad, municipio o región y tendencia temporal.

Se comparará un modelo interpretable de referencia con modelos no lineales. La interpretación deberá mostrar qué variables contribuyen a cada predicción y no solamente entregar una puntuación.

### 3. Potencial municipio–cultivo

Para cada combinación con suficiente soporte se estimará:

- Rendimiento esperado.
- Intervalo de incertidumbre.
- Diferencia respecto al rendimiento actual.
- Similitud con observaciones utilizadas para entrenar el modelo.
- Estabilidad ante escenarios climáticos distintos.

### 4. Escenarios de redistribución

La optimización será una etapa separada del modelo predictivo. Buscará maximizar producción esperada bajo restricciones como:

- No aumentar la superficie agrícola total del municipio.
- Limitar el porcentaje de superficie que puede cambiar de cultivo.
- Conservar cultivos perennes y superficies con fuerte especialización histórica.
- Respetar ciclo y modalidad compatibles.
- Evitar recomendaciones con alta incertidumbre.
- Mantener diversidad productiva mínima.
- Presentar escenarios conservador, intermedio y exploratorio.

Cuando se incorporen datos adicionales podrán añadirse restricciones de agua, rentabilidad, demanda, seguridad alimentaria, rotación y logística.

## Evaluación del modelo

La evaluación debe simular el uso real del modelo y evitar fuga de información.

- Separación temporal: entrenar con años anteriores y evaluar en años posteriores.
- Validación espacial: reservar municipios o regiones completas.
- Métricas por cultivo, ciclo y modalidad, no únicamente una métrica nacional.
- Comparación contra líneas base simples, como media histórica municipal y media regional.
- Evaluación de error en rendimiento y producción.
- Medición de calibración e incertidumbre.
- Revisión especial de combinaciones municipio–cultivo poco observadas.

Una recomendación será más confiable cuando funcione en validación temporal y espacial, tenga suficientes casos comparables y permanezca estable ante varios escenarios climáticos.

## Riesgos metodológicos

- **Correlación no es causalidad:** un suelo o clima asociado con mayor rendimiento no necesariamente lo causa por sí solo.
- **Sesgo de selección:** los cultivos ya se siembran donde productores consideran que pueden funcionar; predecir fuera de esas zonas implica extrapolación.
- **Variables omitidas:** tecnología, agua, infraestructura y decisiones económicas pueden explicar parte importante del rendimiento.
- **Escala municipal:** el clima y el suelo municipal no representan todas las parcelas.
- **Cambios en los registros:** cobertura y calidad pueden variar entre años.
- **Optimización incompleta:** maximizar producción física no equivale a maximizar bienestar, rentabilidad o sostenibilidad.
- **Pérdida de diversidad:** concentrar la producción puede aumentar riesgos climáticos, económicos y biológicos.

## Criterios para una recomendación responsable

Una combinación municipio–cultivo se presentará como oportunidad solamente si:

1. Tiene suficientes observaciones comparables o alta similitud ambiental con casos observados.
2. Su rendimiento esperado supera una referencia claramente definida.
3. La incertidumbre es aceptable.
4. El resultado se mantiene en varios años o escenarios climáticos.
5. No requiere interpretar como causal un factor que no fue medido.
6. La reasignación propuesta es parcial y compatible con restricciones conocidas.

Las combinaciones que no cumplan estos criterios se clasificarán como **sin evidencia suficiente**, no como improductivas.

## Productos esperados

1. Perfil histórico de producción y especialización por municipio.
2. Mapa de rendimiento esperado por cultivo.
3. Comparación entre distribución observada y potencial estimado.
4. Matriz municipio–cultivo con predicción, incertidumbre y soporte de datos.
5. Escenarios de redistribución conservador, intermedio y exploratorio.
6. Lista de municipios eficientes, oportunidades potenciales y casos sin evidencia suficiente.
7. Explicación narrativa de los patrones encontrados y sus limitaciones.

## Estructura del storytelling final

1. **Lo que México produce hoy:** distribución, especialización y cambios entre 2003 y 2025.
2. **Dónde se produce mejor:** municipios con rendimientos altos y estables por cultivo.
3. **Qué explican el clima y el suelo:** asociaciones, sensibilidad y eventos extremos.
4. **La huella de la experiencia:** lugares que superan lo esperado y posibles factores productivos no observados.
5. **Dónde existen oportunidades:** combinaciones municipio–cultivo con potencial y evidencia suficiente.
6. **Qué pasaría con una redistribución parcial:** producción esperada, incertidumbre y restricciones.
7. **Qué no sabemos todavía:** datos faltantes, riesgos y próximos pasos.

## Siguiente etapa

Después de este documento se creará una notebook independiente para preparar los datos de modelado, definir una línea base, entrenar y validar modelos de rendimiento y construir la matriz de potencial municipio–cultivo. La optimización de la distribución se realizará únicamente después de validar que las predicciones sean confiables fuera de muestra.
