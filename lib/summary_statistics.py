import geopandas as gpd
import pandas as pd
from osgeo import ogr
 


def get_gap_summary_statistics(gdb_path, gpkg_gaps_path):
    """
    Calculate gap statistics by status and class.
    
    Returns:
    --------
    dict : {
        'seeding_plant': float (ha),
        'seeding_gap': float (ha),
        'commercial_plant': float (ha),
        'commercial_gap': float (ha),
    }
    """
    paddock_database = gpd.read_file(gdb_path, layer='paddock')
    ds           = ogr.Open(gpkg_gaps_path)
    layers       = [ds.GetLayer(i).GetName() for i in range(ds.GetLayerCount())]
    gapsAR_database = gpd.read_file(gpkg_gaps_path, layer=layers[-1])
    ds           = None     # release OGR handle
    print(gapsAR_database.head(2))

    paddock_database = paddock_database[paddock_database['LANDUSETYP'] == 'CP'][['REGION', 'FARM', 'BLOCK', 'PADDOCK', 'PID', 'Shape_Length', 'Shape_Area', 'geometry']]
    planting_attribute = gpd.read_file(gdb_path, layer='planting')[['PID','MILL', 'VARIETY', 'DATE', 'GROUP', 'OPERATION','Status']]
    simplified_planting = (
        planting_attribute
        .groupby('PID')
        .agg({
            'MILL': 'first',
            'VARIETY': 'first',
            'DATE': 'max',
            'GROUP': lambda x: ', '.join(sorted(x.dropna().astype(str).unique())),
            'OPERATION': lambda x: ', '.join(sorted(x.dropna().astype(str).unique())),
            'Status': 'first'
        })
        .reset_index()
    )

    paddock_base_farmInfo = paddock_database.merge(simplified_planting, on='PID', how='left')
    paddock_base_farmInfo.columns = paddock_base_farmInfo.columns.str.lower()
    gapsAR_database_status = gapsAR_database.merge(
        paddock_base_farmInfo[['pid', 'status']],
        on='pid', how='left'
    )

    # Step 1: Intersect gapsAR_database with paddock_base_farmInfo
    gapsAR_database_status = gpd.overlay(
        gapsAR_database,
        paddock_base_farmInfo[['pid', 'status', 'geometry']],  # include geometry for spatial op
        how='intersection'
    )

    # Step 2: Recalculate area after intersection
    gapsAR_database_status['cls_area_ha'] = gapsAR_database_status.geometry.area / 10000  # m² → ha

    # Summary Return
    seed_plant = sum(gapsAR_database_status[(gapsAR_database_status['status'] == 'Seed Production') & (gapsAR_database_status['cls'] == 'plant')]['cls_area_ha'])
    seed_gap = sum(gapsAR_database_status[(gapsAR_database_status['status'] == 'Seed Production') & (gapsAR_database_status['cls'] == 'gaps spot')]['cls_area_ha'])
    # commercial_plant = sum(gapsAR_database_status[(gapsAR_database_status['status'] == 'Commercial Plantation') & (gapsAR_database_status['cls'] == 'plant')]['cls_area_ha'])
    # commercial_gap = sum(gapsAR_database_status[(gapsAR_database_status['status'] == 'Commercial Plantation') & (gapsAR_database_status['gaps spot'] == 'gaps spot')]['cls_area_ha'])
    commercial_plant = sum(gapsAR_database_status[gapsAR_database_status['cls'] == 'plant']['cls_area_ha']) - seed_plant
    commercial_gap = sum(gapsAR_database_status[gapsAR_database_status['cls'] == 'gaps spot']['cls_area_ha']) - seed_gap

    return seed_plant, seed_gap, commercial_plant, commercial_gap