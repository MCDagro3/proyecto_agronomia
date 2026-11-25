# Proceso de selcción de los puntos para las zonas agricolas.

from config.paths import datapaths
from config.parameters import PREPROCESS_CRS
from preprocess.inegi import principal_shps, complement_shps
import geopandas as gpd
import pandas as pd


def get_agro(df: gpd.GeoDataFrame)-> gpd.GeoDataFrame:
    if "AGECOSIS" in df.columns:
        agro_df = df[df['AGECOSIS']=="AGRICOLA"]
        if agro_df.shape[0] == 0:
            agro_df = df[df['AGECOSIS']=="AGRÍCOLA"]
        return agro_df
    if "DESCRIPCIO" in df.columns:
        agro_values = [c for c in df['DESCRIPCIO'] if c.startswith("AGR")]
        agro_df = df[df['DESCRIPCIO'].isin(agro_values)]
        return agro_df
    if "TIP_INFO" in df.columns:
        agro_df = df[df['TIP_INFO']=="AGRÍCOLA-PECUARIA-FORESTAL"]
    return agro_df


def filter_points(base, new):
    distances = pd.DataFrame(index=base['Centro'], columns=new['Centro'])
    dims = distances.shape
    t = 0
    for p in distances.columns:
        if t % 2000==0:
            print(t / dims[1] * 100)
        distances[p] = base['Centro'].apply(lambda x: x.distance(p)).tolist()
        t+=1
    new_points = distances[distances > 9_000].dropna(axis=1, how="any").columns
    return new_points

def get_agropoints(complement= False):
    for k, file in enumerate(principal_shps):
        print(file)
        if k == 0:
            data = gpd.read_file(file)
            data = data.to_crs(epsg=PREPROCESS_CRS)
            agropoints = get_agro(data)
            agropoints['Centro'] = agropoints.geometry.centroid
            # agropoints['Archivo'] = file.split("/")[-1].replace(".shp","")
            continue
        data = gpd.read_file(file)
        data = data.to_crs(epsg=PREPROCESS_CRS)
        agrodata = get_agro(data)
        agrodata['Centro'] = agrodata.geometry.centroid
        # agropoints['Archivo'] = file.split("/")[-1].replace(".shp","")
        new_points = filter_points(agropoints, agrodata)
        print("Tamaño Actual", agropoints.shape[0])
        print("Puntos Nuevos", new_points.shape[0])
        new_df = agrodata[agrodata['Centro'].isin(new_points)]
        agropoints = pd.concat([agropoints, new_df])
        print("Actualización", agropoints.shape[0])
    if complement:
        print("Agregando puntos complementarios")
        for k, file in enumerate(complement_shps):
            if k == 0:
                df_comp = gpd.read_file(file)
                df_comp = df_comp.to_crs(epsg=PREPROCESS_CRS)
                df_comp.columns = [col.upper() for col in df_comp.columns]
                agro_comp = df_comp[df_comp['TIP_INFO'] =="AGRICOLA-PECUARIA-FORESTAL"]
                continue
            df_comp = gpd.read_file(file)
            df_comp = df_comp.to_crs(epsg=PREPROCESS_CRS)
            df_comp.columns = [col.upper() for col in df_comp.columns]
            agro_comp = pd.concat([agro_comp, df_comp])
        agro_comp['Centro'] = agro_comp.geometry.centroid
        # agro_comp['Archivo'] = file.split("/")[-1].replace(".shp","")
        new_points = filter_points(agropoints, agro_comp)
        print("Tamaño Actual", agropoints.shape[0])
        print("Puntos Nuevos", new_points.shape[0])
        new_df = agrodata[agrodata['Centro'].isin(new_points)]
        agropoints = pd.concat([agropoints, new_df])
    agropoints = agropoints.set_geometry("Centro")
    agropoints = agropoints.drop(columns="geometry")
    agropoints.to_file(datapaths['processed']['INEGI'] / "agropoints.shp")
    return agropoints

get_agropoints()