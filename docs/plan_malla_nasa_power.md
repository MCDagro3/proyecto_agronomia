# Malla de puntos agrícolas con criterio climático NASA POWER

Construir una malla de puntos sobre las zonas agrícolas de México (celdas ≥50% agrícolas en las 7 series USyV, filtradas iterativamente) y anotar cada punto con las features climáticas anuales de NASA POWER por celda, marcando redundancia climática y zonas extremas — todo en archivos nuevos, sin modificar código existente.

## Decisiones del usuario

- **Archivos nuevos únicamente**: `scripts/nasa_malla.py` y `notebooks/nasa_2.ipynb`; no se toca `puntos_agricolas.ipynb`, `scripts/nasa_power.py` ni ningún archivo existente.
- **No hay candidatos previos**: la malla se construye directo de las zonas agrícolas USyV.
- **Iteración**: intersección persistente — una celda sobrevive sólo si es ≥50% agrícola en las **7 series**, filtrando serie por serie (embudo).
- **Cardinalidad**: la malla final incluye **todas** las unidades persistentes; POWER se usa para anotar `zona_clima`, `clima_redundante` y `clima_extremo_*` (no para subconjunto).
- **Resolución**: malla fina propia en EPSG:6372, `GRID_M = 5000` (25 km²/celda), parametrizable.
- **POWER**: parquets diarios por serie ya en `data/interm/NASA/` (años 1981/1985/1993/2002/2007/2015/2018 según mapeo del doc de metodología).

## Estado actual (implementación en curso)

**Completado:**

- Zips USyV extraídos selectivamente a `data/raw/INEGI/usv/serie_{S}/` (~2.2 GB, solo capas agrícolas).
- `scripts/nasa_malla.py` creado y `ruff` limpio. Verificado:
  - `cargar_agricola` carga las 7 series con sus 18 clases en EPSG:6372 (áreas 258k→331k km², caché en `data/interm/NASA/usv_agri/`).
  - `fraccion_agricola('VII')` funciona: malla 407×635 celdas de 5 km, 11 036 celdas ≥50% agrícolas, `mask_sub` 2035×3175 (~108 s; las demás series usarán caché npz).

**Pendiente:**

1. `fraccion_agricola` para series I–VI (~2 min c/u, escribe `data/interm/NASA/malla_frac_{S}_5000.npz`).
2. `filtro_iterativo` → embudo de persistencia + máscara final.
3. `generar_puntos` + `asignar_contexto` + `asignar_clases`.
4. `features_celdas`/`firma_climatica`/`join_clima`/`caracterizar_clima` (KMeans + flags).
5. `exportar` → `data/process/NASA/puntos_malla_clima.{gpkg,csv}` + `embudo_persistencia.csv`.
6. `notebooks/nasa_2.ipynb` (nuevo): orquesta el flujo, muestra embudo, mapa por zona climática, validaciones y limitaciones.
7. Ejecutar la libreta completa con nbclient y verificar salidas.

## Prerrequisitos de datos

- Zips USyV en `data/pure/INEGI/usv_250k_serie_{I..VII}_*.zip`; extraídos a `data/raw/INEGI/usv/serie_{S}/` (solo la capa agrícola de cada zip).
- Capas agrícolas por serie (AGENTS.md):
  - I–II: `us250s{1,2}v` → `TIPO` + `CULT_PRI`/`CULT_SEC`; `.prj` no reconocido → asignar LCC INEGI manual.
  - III–V: capa `g` (`us250s3g.shp`, `us250s4g.shp`, `usv250s5g.shp`) → `TIPAGES` + `TIP_CUL1/2`.
  - VI: `usv250s6_union.shp` → `DESCRIPCIO`. VII: `cdv_usuev250sVII_cnal.shp` → `DESCRIPCIO` (Albers declarado).
  - 18 clases = régimen {R,T,H} × ciclos {A,S,P,AS,AP,SP}; excluir PC/BC.
- Marco Geoestadístico `data/raw/INEGI/Mexico/conjunto_de_datos/00{ent,mun}.shp` (EPSG:6372) para entidad/municipio.

## Diseño del flujo

1. **Extracción USyV**: `extraer_zips()` (idempotente) + `cargar_agricola(serie)` → GeoDataFrame EPSG:6372 con las 18 clases.
2. **Malla base**: rejilla regular de `GRID_M` m sobre el bbox de México en EPSG:6372 (~407×635 celdas a 5 km).
3. **Filtro iterativo serie a serie**: `fraccion_agricola` rasteriza los polígonos a subpíxel (GRID_M/5 = 1 km) y devuelve la fracción por celda; se acumula la intersección `frac ≥ 0.5` y se reporta el embudo (celdas tras cada serie). Caché por serie en `data/interm/NASA/malla_frac_{S}_{GRID_M}.npz`.
4. **Puntos representativos**: por cada celda superviviente, punto = centroide de los subpíxeles agrícolas de la Serie VII dentro de la celda (fallback: centro de celda); coordenadas a WGS84 + EPSG:6372. Columnas: `id_punto`, `frac` implícita, entidad/municipio (sjoin a `00mun.shp`), `clase_{I..VII}` y `clase_estable`.
5. **Clima POWER**:
   - `features_celdas`: agrega cada parquet diario de serie a un registro por celda `(lat, lon)` — `sum` para PRECTOTCORR/FROST_DAYS/CDD0/HDD0, `mean` para el resto; tabla larga en `data/interm/NASA/features_celdas.parquet`.
   - `firma_climatica`: media entre las 7 series por celda y store (merra2/syn1deg) + derivados en merra2 (`pet_mm_anual` desde EVPTRNS, `aridez` = P/PET, `gdd_anual`); caché `firma_climatica.parquet`.
   - `asignar_celdas_power`: celda merra2 por redondeo a 0.5°/0.625° y syn1deg a 1°.
   - `join_clima`: merge de la firma a cada punto (`m_*` merra2, `s_*` syn1deg).
   - `caracterizar_clima`: KMeans (k=10, features estandarizadas) → `zona_clima`; flags `extremo_{var}` en deciles de `m_aridez`, `m_clim_T2M`, `m_clim_PRECTOTCORR`, `m_clim_FROST_DAYS`; `n_puntos_en_celda_merra2` y `clima_redundante`.
6. **Exportación**: `data/process/NASA/puntos_malla_clima.{gpkg,csv}` + `embudo_persistencia.csv`.

## Verificación

- [x] Las 7 capas agrícolas cargan con CRS correcto y 18 clases (hecho: 25 784–35 667 polígonos, 258k–331k km²).
- [x] `fraccion_agricola('VII')` verificada (11 036 celdas ≥50%).
- [ ] Embudo de persistencia decreciente y reportado; total de puntos final en la libreta.
- [ ] Features climáticas plausibles (~2000 celdas × 7 series); 100% puntos con celda POWER asignada.
- [ ] `nasa_2.ipynb` ejecuta completa con nbclient; spot-check celda↔punto.
- [ ] `ruff check` limpio (pasa en el script).

## Riesgos / consideraciones

- **Años POWER vs nominales de serie**: los parquets usan {1981,1985,1993,2002,2007,2015,2018}; las series nominales son {1980,1993,2002,2007,2011,2014,2018}. La firma multiserie lo promedia; re-descargar por año nominal queda como opción.
- **≥50% en las 7 series es exigente**: puede dejar poca área; `UMBRALES` es un dict por serie para relajar si hace falta.
- **Rendimiento**: ~108 s por serie de rasterización (una vez, luego caché); el resto del flujo es rápido.
- **Volumen**: ~11k celdas ≥50% en VII antes de intersectar; la persistencia reducirá el total final.
