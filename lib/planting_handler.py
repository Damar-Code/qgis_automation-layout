import pandas as pd
import  geopandas as gpd

def planting_handler(planting_gdb_path):
    mechanized = gpd.read_file(planting_gdb_path, layer='mechanized')
    manual = gpd.read_file(planting_gdb_path, layer='manual')
    return pd.concat([mechanized, manual], ignore_index=True)