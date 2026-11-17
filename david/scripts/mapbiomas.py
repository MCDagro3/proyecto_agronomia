from scripts.config import DATA_DIR
import pandas as pd
import rasterio
import numpy as np
import os

mapbiome = DATA_DIR / "pure" / "MAPBIOMAS"
files = os.listdir(mapbiome)

for f in files:
    year = f.split("_")[0]
    print(year)
    if os.path.exists(DATA_DIR / "raw" / "MAPBIOMAS" /f"agro_{year}.parquet"):
        print("Año descargado", year)
        continue
    data = rasterio.open(mapbiome / f)
    df = data.read(1)

    use_keys = {19: "Cultivo Anual",
    36: "Cultivo Perenne",
    21: "Mosaico agropecuario"}

    gf = np.isin(df, [19,36,21])

    rows, cols = np.nonzero(gf)
    lons, lats = rasterio.transform.xy(data.transform, rows, cols)

    map_biomes_map = pd.DataFrame({"lon": lons, "lat": lats, "clase_id": df[rows, cols]})
    map_biomes_map['id_name'] = map_biomes_map['clase_id'].apply(lambda x: use_keys[x])

    map_biomes_map.to_parquet(DATA_DIR / "raw" / "MAPBIOMAS" /f"agro_{year}.parquet")
