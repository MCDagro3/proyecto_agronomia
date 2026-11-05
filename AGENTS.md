# Notas del proyecto

## Entorno

- Python del proyecto: `.venv/bin/python` (tiene geopandas, shapely, rasterio,
  pyproj, duckdb, nbformat, nbclient, ipykernel). El Python del sistema **no** tiene
  estas librerías.
- Ejecutar una libreta de punta a punta (equivalente a `nbconvert --execute`):
  ```bash
  .venv/bin/python -c "
  import nbformat, nbclient
  nb = nbformat.read('notebooks/puntos_agricolas.ipynb', as_version=4)
  nbclient.NotebookClient(nb, timeout=600, kernel_name='python3',
                          resources={'metadata': {'path': '.'}}).execute()
  nbformat.write(nb, 'notebooks/puntos_agricolas.ipynb')"
  ```

## Datos

- Etapas: `data/pure` (descargas), `data/raw` (legibles), `data/interm` (cachés),
  `data/process` (salidas). `data/` está en `.gitignore`.
- Rutas: siempre relativas a `scripts.config.DATA_DIR`; no usar rutas absolutas.

## Mapas INEGI USyV 1:250 000 (Series I–VII)

- Capa agrícola por serie: I–II `us250s{1,2}v` (`TIPO` + `CULT_PRI`/`CULT_SEC`);
  III–V capa `g` (`TIPAGES` + `TIP_CUL1`/`TIP_CUL2`); VI `usv250s6_union`;
  VII `cdv_usuev250sVII_cnal` (`DESCRIPCIO`).
- 18 clases agrícolas: régimen {R,T,H} × ciclos {A,S,P,AS,AP,SP}; se excluyen PC y BC.
- CRS: I–II traen `.prj` proj4 que GDAL no reconoce → asignar LCC INEGI manual
  (`+proj=lcc +ellps=GRS80 +lat_0=12 +lon_0=-102 +lat_1=17.5 +lat_2=29.5 +x_0=2500000 +y_0=0`).
  III–VI son LCC ITRF92. VII es **Albers** (declarado y comprobado: ~84% de
  coincidencia con VI vs ~32% si se leyera como LCC). CRS de trabajo: EPSG:6372.
- Encodings: Serie I usa ISO-8859-1; campos numéricos legacy tienen decimales con
  coma (pyogrio advierte) — no depender de `AREA`/`PERIMETER`/`CODIGO`.
- La libreta `notebooks/puntos_agricolas.ipynb` guarda cachés en
  `data/interm/INEGI/usv_agri_serie_*.parquet` y `candidatos_*.parquet`.

## Salidas

- `data/process/INEGI/puntos_agricolas.{gpkg,csv}`: 1002 puntos (N*=1000 según curva
  de representatividad), las 18 clases, los 32 estados, trayectorias de clase
  I→VII con seguimiento de cambios de ciclo y régimen.
- `data/process/INEGI/puntos_agricolas_seguimiento.csv`: formato largo, 7 filas por punto.

## Precauciones

- `.env` contiene una llave de WeatherAPI; no exponerla.
- No commitear salidas de `data/` (gitignored).
