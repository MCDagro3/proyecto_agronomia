# Metodología: estimar clases agrícolas INEGI desde MapBiomas

Guía metodológica para estimar anualmente (1985–2025) las clases agrícolas de
INEGI USyV —régimen Riego/Temporal/Humedad × ciclo Anual/Semipermanente/Permanente—
usando MapBiomas como predictor y las series INEGI I–VII como etiquetas
multitemporales de referencia.

## 1. Objetivo

Reconstruir, para cada año 1985–2025 y a nivel nacional, la distribución espacial
de las **18 clases agrícolas de INEGI**
(`AGRICULTURA DE {RIEGO, TEMPORAL, HUMEDAD} × {ANUAL, SEMIPERMANENTE, PERMANENTE}`
+ combinaciones), que INEGI solo publica como fotos vectoriales cada ~5–7 años.
El producto: mapas anuales clasificados y superficies por municipio×año, unibles
a SIAP por `CVEGEO`.

## 2. Idea rectora

Una clase agrícola INEGI se factoriza en tres decisiones independientes:

```
clase_INEGI = [¿es agricultura?] × [régimen: riego|temporal|humedad] × [ciclo: anual|semiperm.|permanente|mixto]
```

Cada factor se estima con la fuente que mejor lo resuelve:

| Factor | Fuente principal | Dificultad |
|---|---|---|
| Máscara agrícola | MapBiomas (19, 36, 21) | Baja — MB mapea cultivo directo |
| Ciclo del cultivo | MapBiomas (19→anual, 36→permanente) | Media — semipermanente y mixtos no existen en MB |
| Régimen hídrico | Nada en MB → modelo con covariables | Alta — es el núcleo del trabajo |

INEGI aporta la **verdad de entrenamiento multitemporal** (series II–VII ≈ 1985,
1993, 2002, 2007, 2015, 2018); MapBiomas aporta la **serie anual** que falta.

## 3. Insumos

| Insumo | Uso | Estado |
|---|---|---|
| MapBiomas MX Col.1, anual 30m | predictor base (máscara+ciclo) | descargado |
| INEGI USyV series II–VII (vectores) | etiquetas por época | descargable con `scripts/inegi_mapas.py` |
| `00mun.shp` (CVEGEO, EPSG:6372) | agregación municipal | en `data/raw/INEGI/Mexico/` |
| Normales climáticas raster (`preload/…/norm9120*.tif`) | covariable aridez | en repo |
| SIAP `Nommodalidad` por municipio (2003+) | covariable % riego/temporal | en `data/process/DGSIAP/ProdAgro_*_mun.csv` |
| DEM (INEGI CEM o SRTM) + fisiografía/ecorregiones | covariables estáticas | por descargar |
| (Opcional) Máscara de riego CONABIO / FAO-GMIA | predictor fuerte de riego | por descargar, muy recomendable |

## 4. Pasos metodológicos

### Paso 1 — Armonizar etiquetas entre series
- Construir la tabla `clave_INEGI → (régimen, ciclo)` por serie. **Verificar la
  leyenda real de series I–III**: usan diccionario distinto al de IV–VII y
  probablemente NO desglosan ciclo → solo aportan régimen.
- Decidir el tratamiento de clases mixtas (`ANUAL Y PERMANENTE`, etc.): como
  clase propia ("mixto") o repartiendo el polígono 50/50 según composición de
  píxeles MB (19 vs 36).
- Serie I (~1980) queda fuera del rango MB → excluir o usar solo para
  comparaciones cualitativas.

### Paso 2 — Emparejamiento espacio-temporal
- Reproyectar cada serie INEGI al CRS/grilla de MapBiomas y rasterizar **solo
  polígonos `AGRICULTURA*`** (etiqueta = clave; resto = `no_agricola`).
- Emparejar cada serie con el año MB más cercano: II→1985, III→1993, IV→2002,
  V→2007, VI→2015, VII→2018. Ojo: el año nominal de cada serie es difuso
  (fotointerpretación multianual) — tolerar ±1 año y documentarlo.

### Paso 3 — Matriz de contingencia MB × INEGI (diagnóstico)
- Cruzar clases MB del año emparejado contra claves INEGI por época. Esto mide
  qué fracción de la agricultura INEGI cae en MB{19,36,21,15} y con qué "pureza"
  por régimen.
- Salida conceptual: tabla `P(régimen_INEGI | clase_MB)` por época y por región —
  **primer estimador usable ya a mano**.

### Paso 4 — Reglas de máscara y ciclo
- **Máscara**: MB∈{19,36} → agrícola. MB=21 (mosaico) y MB=15 (pastizal
  cultivado) se aceptan con probabilidad leída de la contingencia (o se excluyen
  si la pureza es baja). Decisión de diseño a fijar tras ver el Paso 3.
- **Ciclo**: 19→ANUAL, 36→PERMANENTE. SEMIPERMANENTE no existe en MB → estimarla
  donde la contingencia la concentre (típicamente píxeles 36 en zonas de
  cultivos plurianuales) o colapsarla con permanente si su soporte es bajo.
  Clases mixtas se resuelven por la regla del Paso 1.

### Paso 5 — Estimar el régimen (R/T/H): el núcleo
Riego es tecnológico/económico, no espectral → se estima con contexto, no con el
píxel solo.

- **Muestra de entrenamiento**: píxeles **interiores** de polígonos R*/T*/H* de
  cada serie (erosión/buffer negativo — la escala 1:250k hace los bordes poco
  confiables a 30m).
- **Covariables**:
  - Estáticas: elevación y pendiente (riego favorece llanuras), distancia a
    cuerpos de agua/ríos, región fisiográfica, normales de
    precipitación/temperatura (riego correlaciona con aridez).
  - Dinámicas: % de superficie de riego del municipio según SIAP del año
    (contexto municipal fuerte); antes de 2003 usar el valor más cercano
    disponible.
- **Modelo**: clasificador de 3 clases (R/T/H) que devuelva probabilidades —
  Random Forest o boosting son adecuados; un enfoque aún más simple y defendible
  es una **tabla de desagregación probabilística**
  `P(régimen | clase_MB, bins de covariables, estado/región)` estimada directo
  del cruce, sin ML.
- **Humedad** (cultivo sobre humedad residual, p.ej. tablas/lagunas): píxeles
  planos, próximos a agua o ex-cuerpos lacustres — tratarla como clase con prior
  espacial fuerte.

### Paso 6 — Extrapolación anual
- Por cada año t: MB(t) → máscara y ciclo; covariables dinámicas del año (SIAP
  municipal; si falta, el año más cercano) + estáticas → régimen.
- Ensamblar `clase = máscara × régimen × ciclo`; conservar la probabilidad como
  medida de confianza.

### Paso 7 — Agregación municipal
- Conteo de píxeles por `CVEGEO` → hectáreas por `régimen × ciclo × año`; unir a
  SIAP/`agromodel` por `CVEGEO + año`.

## 5. Validación (a mano, en este orden)

1. **Contingencia**: pureza de la máscara y consistencia régimen↔MB por época.
2. **Holdout espacial**: entrenar excluyendo municipios/tiles completos →
   matriz de confusión de régimen; F1 por clase (esperar
   humedad < riego < temporal).
3. **Transferencia temporal**: entrenar con S7(2018), predecir la época S5(2007)
   y comparar contra la serie real → mide si el estimador viaja en el tiempo
   (crítico para 1985–2002).
4. **Superficies municipales**: ha estimadas vs INEGI 2018 por municipio →
   R²/MAE por régimen.
5. **Cordura externa**: totales agrícolas estimados vs superficie sembrada SIAP
   por año (deben correlacionar fuerte, no necesariamente igualar).

## 6. Limitaciones a documentar

- Escalas distintas (1:250k vs 30m) → solo píxeles interiores como
  entrenamiento; bordes tienen ruido heredado.
- `SEMIPERMANENTE` y `HUMEDAD` son las clases más débiles — reportar confianza
  por clase.
- % riego SIAP es agregado municipal (no pixel) y solo existe desde 2003 → la
  variación temporal pre-2003 está subestimada.
- Errores de MapBiomas Col.1 (primera versión) se propagan a la máscara y al
  ciclo.
- El estimador de régimen aprende correlaciones espaciales de 2018; la
  transferencia temporal (Paso 5.3) es la prueba decisiva de si el enfoque
  sirve para años remotos.

## 7. Decisiones de diseño que debes tomar

1. Incluir MB 21/15 en la máscara o no (según pureza del Paso 3).
2. Colapsar `SEMIPERMANENTE` con permanente vs. intentar estimarla.
3. Mínimo soporte por clase para conservarla (recomendado: agrupar claves con
   <~0.5% del área agro en su régimen).
4. Modelo ML vs tabla de desagregación probabilística — empezar por la tabla
   (Paso 3 ya la produce) y escalar a ML solo si la precisión no basta.
5. Si el riego municipal SIAP no baja bien a pixel, evaluar la máscara
   CONABIO/GMIA como covariable.

## 8. Orden sugerido de trabajo

1. Descargar series II–VII, inspeccionar leyendas reales (Paso 1).
2. Emparejamiento + contingencia (Pasos 2–3) — con esto ya tienes el estimador
   más simple.
3. Máscara + ciclo anual (Paso 4).
4. Régimen: primero tabla probabilística, luego modelo si hace falta (Paso 5).
5. Validaciones en el orden del §5 antes de generar la serie completa.
6. Serie anual + agregación municipal (Pasos 6–7).
