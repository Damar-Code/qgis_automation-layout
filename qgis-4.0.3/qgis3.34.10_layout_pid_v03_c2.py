from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsPrintLayout,
    QgsLayoutItemMap,
    QgsLayoutExporter,
    QgsUnitTypes,
    QgsVectorLayer,
    QgsLayoutSize,
    QgsCoordinateReferenceSystem,
    QgsLayoutPoint,
    QgsLayoutMeasurement,
    QgsRectangle,
    QgsFillSymbol,
    QgsLayoutItemPicture,
    QgsPalLayerSettings,
    QgsVectorLayerSimpleLabeling,
    QgsTextFormat,
    QgsLayoutItemShape,
    QgsSimpleFillSymbolLayer,
    QgsProperty,
    QgsLayoutItemPage,
    QgsGeometry,
    QgsFeature,
    )

from qgis.PyQt.QtCore import (
    Qt,
)

from qgis.PyQt.QtGui import (
    QColor,
    QImage,
)

import pandas as pd
import geopandas as gpd
import numpy as np
from PIL import Image as PILImage
from datetime import date, datetime
import os
import fiona
import yaml
import math
from pathlib import Path
import sys
import tempfile
import traceback

# Allow importing local helpers from the repository root
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

lib_dir = os.path.join(project_root, 'lib')
if str(lib_dir) not in sys.path:
    sys.path.append(str(lib_dir))

from germination_table_img import create_gap_table_image, create_land_application_table_image
from planting_handler import planting_handler
from legend_img import create_land_status_legend_image

qml_dir = os.path.join(project_root, 'qml')
img_dir = os.path.join(project_root, 'img')

# ── CONFIGURATION ──────────────────────────────────────────────────────────────
configuration_variable_path = os.path.join(project_root, 'config.yaml')
with open(configuration_variable_path, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

qgis_apps           = cfg['qgis_apps']
c2                  = cfg['companies_alias']['c2']

today = date.today()
run_day = today.strftime("%d %B %Y")
run_day_ymd = today.strftime("%Y%m%d")

# ── Export formats: any combination of 'pdf', 'jpg' ────────────────────────────
EXPORT_FORMATS = ['pdf'] # 'jpg'

# ── Commercial-plantings filter for c2 (MNM) ────────────────────────────────────
# 'date'   : plant_date on/after COMMERCIAL_DATE_CUTOFF counts as commercial
#            (gap_layer), before it counts as seed (seed_layer).
# 'status' : the original Status == COMMERCIAL_STATUS_VALUE / 'Seed Production'
#            filter, kept available for when it's needed again later.
COMMERCIAL_FILTER_MODE  = 'date'  # 'date' or 'status'
COMMERCIAL_DATE_CUTOFF  = '2026-05-01'
COMMERCIAL_STATUS_VALUE = 'Commercial'

# Page 2's simple summary table (Planted/Soil Rehabilitation/Land Application
# Status) is rendered at the same mm-per-matplotlib-inch scale as page 1's
# germination table (rather than a fixed size), so it stays visually
# proportioned like page 1's table even though its own natural width varies
# by PID (content-tidy column widths). Mirrors page 1's full (table +
# classification) image width in germination_table_img.py: table_w=13.7,
# gap_w=0.15, cls_col1_w=1.3, cls_col2_w=2.3, right_margin=0.15.
FULL_TABLE_FIG_W_INCHES = 13.7 + 0.15 + 1.3 + 2.3 + 0.15

# Land Application Status legend: wraps into a new column every this many
# categories (see create_land_status_legend_image), rendered at a single
# fixed mm-per-matplotlib-inch scale (LAND_STATUS_LEGEND_SCALE_MM_PER_INCH)
# so every PID's swatches/text render at the exact same size regardless of
# how many categories or columns it has — instead of being stretched/shrunk
# to fit a target width, which made swatch sizes vary between PIDs.
LAND_STATUS_LEGEND_MAX_ROWS_PER_COL = 8
LAND_STATUS_LEGEND_DPI = 150
# Sized so a full 8-row column (title_h=0.7 + top_margin=0.15 + 8*row_h=0.6 +
# 0.1, matching _render_legend_image's own constants) always fits within the
# worst-case available vertical space below the main map (germination_y=450
# to the page's bottom margin at 594-5=589), with no further shrinking needed.
LAND_STATUS_LEGEND_SCALE_MM_PER_INCH = (594.0 - 450.0 - 5.0) / (0.7 + 0.15 + 8 * 0.6 + 0.1)

def _top_content_margin_fraction(image_path, threshold=200):
    """Fraction of image height that is blank margin above the first visible
    (non-white) row — used to align two images' visible content/borders
    regardless of matplotlib's own internal top padding."""
    try:
        arr = np.array(PILImage.open(image_path).convert('L'))
    except Exception:
        return 0.0
    for y in range(arr.shape[0]):
        if (arr[y] < threshold).any():
            return y / arr.shape[0]
    return 0.0

def run_single_company(companies_select, pid, paddock_cucp_path, paddock_cp_path, gap_status_path, germination_img_path, germination_img_path_page2, land_status_legend_img_path, variety_index_map) -> None:
    print('PID: ', pid)

    map_path         = cfg['companies'][companies_select]['map_path']
    gdb_path         = cfg['companies'][companies_select]['gdb_path']
    land_status_path = cfg['companies'][companies_select]['land_status_path']
    soil_rehab_path  = cfg['companies'][companies_select]['soil_rehabilitation_path']

    # Ensure project is fresh for each run
    project = QgsProject.instance()
    project.clear()

    # CREATE QGIS PROJECT
    project = QgsProject.instance()
    project.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

    # PRODUCE LAYOUTING MANAGER
    manager = project.layoutManager()
    layout_name = "Automation Map"
    layout = manager.layoutByName(layout_name)
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(layout_name)
    manager.addLayout(layout)

    # ── A1 LANDSCAPE PAGE ────────────────────────────────────────────────────
    page = layout.pageCollection().page(0)
    page.setPageSize(QgsLayoutSize(841, 594, QgsUnitTypes.LayoutMillimeters))

    # Page 2 (currently a complete duplicate of page 1; specific layers will
    # be swapped out for land_status / soil_rehabilitation in a later step).
    page2 = QgsLayoutItemPage(layout)
    page2.setPageSize(QgsLayoutSize(841, 594, QgsUnitTypes.LayoutMillimeters))
    layout.pageCollection().addPage(page2)

    # Builds one full report page (main map + map index + germination table +
    # legend + bounding frame) on the given page index (0 = page 1, 1 = page 2).
    # Each call creates its own fresh layer instances so the two pages don't
    # share/fight over the same layer objects.
    def build_report_page(page_index):

        ## Gap Database — commercial plantings (joined in from the planting
        ## database in main(), once per company run). Filtered either by plant_date
        ## cutoff or by Status, depending on COMMERCIAL_FILTER_MODE.
        # On page 2, the gap layer is replaced with Land Status (styled with
        # landstatusStyle.qml) instead of gap detection.
        is_land_status_page = (page_index == 1)
        soil_rehab_layer = None
        if is_land_status_page:
            fiona_latest_land_status = fiona.listlayers(land_status_path)[-1]
            gap_layer = QgsVectorLayer(
                f"{land_status_path}|layername={fiona_latest_land_status}",
                "Land Status",
                "ogr"
            )
            gap_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
            gap_layer.setSubsetString(f"\"PID\" = '{pid}'")

            ## Soil Rehabilitation — drawn above Land Status, clipped to the
            ## selected PID's boundary. Any feature overlapping the PID is
            ## included, but its geometry is cut to the PID edge instead of
            ## being shown in full.
            pid_boundary_layer = QgsVectorLayer(
                f"{paddock_cucp_path}|layername=paddock_cucp",
                "PID Boundary (tmp)",
                "ogr"
            )
            pid_boundary_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
            pid_boundary_layer.setSubsetString(f"\"PID\" = '{pid}'")
            pid_geom = QgsGeometry()
            for feature in pid_boundary_layer.getFeatures():
                geom = feature.geometry()
                if geom is not None and not geom.isEmpty():
                    pid_geom = geom if pid_geom.isEmpty() else pid_geom.combine(geom)

            soil_rehab_source = QgsVectorLayer(
                f"{soil_rehab_path}|layername=soil_rehabilitation",
                "Soil Rehabilitation Source",
                "ogr"
            )
            soil_rehab_source.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

            soil_rehab_layer = QgsVectorLayer(
                "Polygon?crs=EPSG:32754",
                "Soil Rehabilitation",
                "memory"
            )
            soil_rehab_layer.dataProvider().addAttributes(soil_rehab_source.fields())
            soil_rehab_layer.updateFields()

            clipped_features = []
            if not pid_geom.isEmpty():
                for feature in soil_rehab_source.getFeatures():
                    geom = feature.geometry()
                    if geom is None or geom.isEmpty() or not geom.intersects(pid_geom):
                        continue
                    clipped_geom = geom.intersection(pid_geom)
                    if clipped_geom is None or clipped_geom.isEmpty():
                        continue
                    new_feature = QgsFeature(soil_rehab_layer.fields())
                    new_feature.setGeometry(clipped_geom)
                    new_feature.setAttributes(feature.attributes())
                    clipped_features.append(new_feature)

            soil_rehab_layer.dataProvider().addFeatures(clipped_features)
            soil_rehab_layer.updateExtents()

            soil_rehab_layer.loadNamedStyle(os.path.join(qml_dir, "soilRehabilitationStyle.qml"))
        else:
            gap_layer = QgsVectorLayer(
                f"{gap_status_path}|layername=gap_status",
                "Gap Detection",
                "ogr"
            )
            gap_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
            if COMMERCIAL_FILTER_MODE == 'date':
                gap_layer.setSubsetString(
                    f"\"pid\" = '{pid}' AND \"plant_date\" >= '{COMMERCIAL_DATE_CUTOFF}'"
                )
            else:
                gap_layer.setSubsetString(
                    f"\"pid\" = '{pid}' AND \"Status\" = '{COMMERCIAL_STATUS_VALUE}'"
                )

        ## Seed layer: same gap detection source, but the complementary filter —
        ## plant_date before the cutoff, or Status = 'Seed Production'.
        seed_layer = QgsVectorLayer(
            f"{gap_status_path}|layername=gap_status",
            "Seed",
            "ogr"
        )
        seed_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
        if COMMERCIAL_FILTER_MODE == 'date':
            seed_layer.setSubsetString(
                f"\"pid\" = '{pid}' AND \"plant_date\" < '{COMMERCIAL_DATE_CUTOFF}'"
            )
        else:
            seed_layer.setSubsetString(f"\"pid\" = '{pid}' AND \"Status\" = 'Seed Production'")

        ## Infrastructure Database - filtered to the road layer only
        road_layer = QgsVectorLayer(
            f"{gdb_path}|layername=road",
            "Road",
            "ogr"
        )
        road_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

        ## Infrastructure Database - filtered to the drainage layer only
        drainage_layer = QgsVectorLayer(
            f"{gdb_path}|layername=drainage",
            "Drainage",
            "ogr"
        )
        drainage_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

        ## Paddock CU/CP merged-by-PID layer (built once in main(), read per PID here)
        paddock_cucp_layer = QgsVectorLayer(
            f"{paddock_cucp_path}|layername=paddock_cucp",
            "Paddock CUCP",
            "ogr"
        )
        paddock_cucp_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

        ## Paddock CU/CP Selected
        paddock_selected_layer = QgsVectorLayer(
                f"{paddock_cucp_path}|layername=paddock_cucp",
                "Paddock CUCP",
                "ogr"
            )
        paddock_selected_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
        paddock_selected_layer.setSubsetString(f"\"PID\" = '{pid}'") # Filter only selected PID

        ## Paddock CP merged-by-PID layer (built once in main(), read per PID here)
        paddock_cp_layer = QgsVectorLayer(
            f"{paddock_cp_path}|layername=paddock_cp",
            "Paddock CP",
            "ogr"
        )
        paddock_cp_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
        paddock_cp_layer.setSubsetString(f"\"PID\" = '{pid}'") # Filter only selected PID

        ## Water Body
        wb_layer = QgsVectorLayer(
            f"{gdb_path}|layername=paddock",
            "Water Body",
            "ogr"
        )
        wb_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
        wb_layer.setSubsetString(f"\"LANDUSETYP\" = 'WB'") # Filter only selected PID

        # MAIN MAP SETTING
        ## Setup Main Map Frame & Call All Layers, covering the full A1 page
        def add_mainMap():

            # Load the styles
            ## Gap (or Land Status, on page 2)
            gap_layer_style_path = os.path.join(
                qml_dir, "landstatusStyle.qml" if is_land_status_page else "gapsAreaStyle.qml"
            )
            gap_layer.loadNamedStyle(gap_layer_style_path)

            ## Label each gap feature with the same "(N)" index shown next to its
            ## variety's planting period in the germination summary table.
            ## Must be set AFTER loadNamedStyle(), since the QML's
            ## styleCategories="AllStyleCategories" resets labeling when loaded.
            ## Not applicable to the Land Status layer on page 2.
            if variety_index_map and not is_land_status_page:
                map_pairs = ",".join(
                    f"'{str(var).replace(chr(39), chr(39) * 2)}',{idx}"
                    for var, idx in variety_index_map.items()
                )
                label_expression = f"'(' || map_get(map({map_pairs}), \"variety\") || ')'"

                pal_settings = QgsPalLayerSettings()
                pal_settings.fieldName = label_expression
                pal_settings.isExpression = True
                text_format = QgsTextFormat()
                text_format.setSize(15)  
                pal_settings.setFormat(text_format)

                gap_layer.setLabeling(QgsVectorLayerSimpleLabeling(pal_settings))
                gap_layer.setLabelsEnabled(True)

            QgsProject.instance().addMapLayer(gap_layer)
            ## Soil Rehabilitation (page 2 only) — drawn above Land Status
            if soil_rehab_layer is not None:
                QgsProject.instance().addMapLayer(soil_rehab_layer)
            ## Seed
            # On page 2, Seed Production is muted to match the merged
            # "Planted" gray entry in legend_p2.png (page 1 keeps its own color).
            seed_symbol = QgsFillSymbol.createSimple({
                "color": "#d0d0d0" if is_land_status_page else "#ffc986",
                "outline_style": "no",
            })
            seed_layer.renderer().setSymbol(seed_symbol)
            QgsProject.instance().addMapLayer(seed_layer)
            ## Paddock CUCP
            paddock_cucp_style_path = os.path.join(qml_dir, "selectedPIDStyle.qml")
            paddock_selected_layer.loadNamedStyle(paddock_cucp_style_path)
            QgsProject.instance().addMapLayer(paddock_selected_layer)
            ## Paddock CUCP
            paddock_cucp_style_path = os.path.join(qml_dir, "cucpStyle.qml")
            paddock_cucp_layer.loadNamedStyle(paddock_cucp_style_path)

            # The QML labels every PID's polygon. Keep its symbology and label
            # formatting exactly as-is, but only show the label for the PID
            # actually being run in this map, not every PID in the layer.
            cucp_labeling = paddock_cucp_layer.labeling()
            if cucp_labeling is not None:
                cucp_pal_settings = cucp_labeling.settings()
                escaped_pid = pid.replace("'", "''")
                cucp_pal_settings.dataDefinedProperties().setProperty(
                    QgsPalLayerSettings.Property.Show,
                    QgsProperty.fromExpression(f"\"PID\" = '{escaped_pid}'")
                )
                paddock_cucp_layer.setLabeling(QgsVectorLayerSimpleLabeling(cucp_pal_settings))

            QgsProject.instance().addMapLayer(paddock_cucp_layer)
            ## Paddock CP
            # On page 2, Next Target is muted to match the merged "Planted"
            # gray entry in legend_p2.png (page 1 keeps its own color).
            paddock_cp_symbol = QgsFillSymbol.createSimple({
                "color": "#d0d0d0" if is_land_status_page else "#e2ff9f",
                "outline_style": "no",
            })
            paddock_cp_layer.renderer().setSymbol(paddock_cp_symbol)
            QgsProject.instance().addMapLayer(paddock_cp_layer)
            ## Road
            road_layer_style_path = os.path.join(qml_dir, "RoadGISStyle.qml")
            road_layer.loadNamedStyle(road_layer_style_path)
            QgsProject.instance().addMapLayer(road_layer)
            ## Drainage
            drainage_layer_style_path = os.path.join(qml_dir, "drainageStyle.qml")
            drainage_layer.loadNamedStyle(drainage_layer_style_path)
            QgsProject.instance().addMapLayer(drainage_layer)
            ## Water Body
            wb_layer_style_path = os.path.join(qml_dir, "waterBodyStyle.qml")
            wb_layer.loadNamedStyle(wb_layer_style_path)
            QgsProject.instance().addMapLayer(wb_layer)

            map_item = QgsLayoutItemMap(layout)
            # Draw order (first = topmost): road, drainage, paddock CUCP, paddock CP, then gap.
            # paddock_cp_layer must sit above gap_layer, since gap_layer's opaque
            # "gaps spot"/"plant" fills would otherwise fully cover it.
            # On page 2, soil_rehab_layer sits above gap_layer (which holds Land Status).
            map_layers = [road_layer, drainage_layer, paddock_selected_layer]
            if soil_rehab_layer is not None:
                map_layers.append(soil_rehab_layer)
            map_layers += [gap_layer, seed_layer, paddock_cp_layer, paddock_cucp_layer, wb_layer]
            map_item.setLayers(map_layers)

            # Cover the top 75% of the A1 page; the bottom 25% is left blank
            # for the picture table to be added later.
            map_item.attemptMove(QgsLayoutPoint(2.366, 2.412, QgsUnitTypes.LayoutMillimeters), page=page_index)
            map_item.attemptResize(QgsLayoutSize(836.034, 445.5, QgsUnitTypes.LayoutMillimeters))

            # IMPORTANT
            # Some PIDs can produce an empty or invalid layer extent; in that case the
            # map scale becomes NaN and math.ceil() fails. We fail early with a clear
            # message so the PID loop can log and continue with a detailed diagnosis.
            paddock_cucp_count = paddock_selected_layer.featureCount()
            if paddock_cucp_count <= 0:
                debug_msg = (
                    f"PID debug: pid={pid}, company={companies_select}, "
                    f"paddock_selected_layer_name={paddock_selected_layer.name()}, paddock_selected_layer_count={paddock_cucp_count}, "
                    f"filter='PID = {pid}'"
                )
                raise ValueError(f"PID {pid} not found in paddock_selected_layer or paddock_selected_layer is empty after filtering. | {debug_msg}")

            # NOTE: layer.extent() can incorrectly return a null extent on a
            # subset-filtered GeoPackage layer when an rtree spatial index is present
            # (a known OGR/GPKG provider quirk: the index-based fast path ignores the
            # subsetString WHERE clause). Compute the extent directly from the
            # filtered features instead of trusting the cached/indexed extent.
            extent = QgsRectangle()
            for feature in paddock_selected_layer.getFeatures():
                geom = feature.geometry()
                if geom is not None and not geom.isEmpty():
                    extent.combineExtentWith(geom.boundingBox())
            extent_valid = not extent.isNull() and (
                math.isfinite(extent.xMinimum()) and
                math.isfinite(extent.xMaximum()) and
                math.isfinite(extent.yMinimum()) and
                math.isfinite(extent.yMaximum()) and
                extent.width() > 0 and
                extent.height() > 0
            )

            if not extent_valid:
                debug_msg = (
                    f"PID debug: pid={pid}, company={companies_select}, "
                    f"paddock_selected_layer_count={paddock_cucp_count}, paddock_cucp_extent_isNull={extent.isNull()}, "
                    f"paddock_cucp_extent={str(paddock_selected_layer.extent())}"
                )
                raise ValueError(
                    f"PID {pid} has no valid map extent in paddock_selected_layer. | {debug_msg}"
                )

            extent.scale(1.1) # 10% margin
            map_item.zoomToExtent(extent)

            # Round up scale
            current_scale = map_item.scale()
            if not math.isfinite(current_scale) or current_scale <= 0:
                debug_msg = (
                    f"PID debug: pid={pid}, company={companies_select}, "
                    f"paddock_selected_layer_count={paddock_cucp_count}, current_scale={current_scale}, "
                    f"extent={extent.asWkt() if hasattr(extent, 'asWkt') else str(extent)}"
                )
                raise ValueError(
                    f"PID {pid} produced an invalid map scale after zooming to extent. | {debug_msg}"
                )
            rounded_scale = math.ceil(current_scale / 1000) * 1000
            map_item.setScale(rounded_scale)

            map_item.setFrameEnabled(True)
            map_item.setFrameStrokeColor(QColor(0, 0, 0))
            map_item.setFrameStrokeWidth(QgsLayoutMeasurement(0.5, QgsUnitTypes.LayoutMillimeters))
            map_item.setKeepLayerSet(True)
            map_item.setKeepLayerStyles(True)

            layout.addLayoutItem(map_item)

            map_item.refresh()

            return map_item

        map_item = add_mainMap()

        # MAP INDEX (overlay inset in the main map's bottom-left corner): Farm and
        # Block boundaries, with the run PID's paddock highlighted in yellow.
        def add_mapIndex():
            farm_layer = QgsVectorLayer(
                f"{gdb_path}|layername=Farm",
                "Farm Index",
                "ogr"
            )
            farm_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
            farm_style_path = os.path.join(qml_dir, "farmGermStyle.qml")
            farm_layer.loadNamedStyle(farm_style_path)
            QgsProject.instance().addMapLayer(farm_layer)

            block_layer = QgsVectorLayer(
                f"{gdb_path}|layername=Block",
                "Block Index",
                "ogr"
            )
            block_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
            block_style_path = os.path.join(qml_dir, "blockStyle.qml")
            block_layer.loadNamedStyle(block_style_path)
            QgsProject.instance().addMapLayer(block_layer)

            # The selected PID's paddock boundary, styled just for this index map
            # (a separate layer instance so the main map's own styling is untouched).
            index_selected_layer = QgsVectorLayer(
                f"{paddock_cucp_path}|layername=paddock_cucp",
                "Selected PID Index",
                "ogr"
            )
            index_selected_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
            index_selected_layer.setSubsetString(f"\"PID\" = '{pid}'")
            index_symbol = QgsFillSymbol.createSimple({
                "color": "#ffff00",
                "outline_color": "#000000",
                "outline_width": "0.2",
            })
            index_selected_layer.renderer().setSymbol(index_symbol)
            QgsProject.instance().addMapLayer(index_selected_layer)

            index_map = QgsLayoutItemMap(layout)
            index_map.setLayers([index_selected_layer, block_layer, farm_layer])

            # Match the frame's own aspect ratio to the Farm extent's aspect ratio,
            # so the content fills the frame edge-to-edge with no letterbox gap —
            # otherwise QGIS pads the shorter axis symmetrically, which reads as
            # an uneven left-vs-bottom margin even though the outer box position
            # itself is centered correctly.
            farm_extent = farm_layer.extent()
            farm_aspect = farm_extent.width() / farm_extent.height()
            index_w = 90.0 * 1.3  # 30% larger
            index_h = index_w / farm_aspect

            margin = 5.0
            main_map_x, main_map_y = 2.366, 2.412
            main_map_h = 445.5
            index_x = main_map_x + margin
            index_y = main_map_y + main_map_h - margin - index_h

            index_map.attemptMove(QgsLayoutPoint(index_x, index_y, QgsUnitTypes.LayoutMillimeters), page=page_index)
            index_map.attemptResize(QgsLayoutSize(index_w, index_h, QgsUnitTypes.LayoutMillimeters))

            # The map extent follows the Farm layer's own extent, not the selected PID.
            index_map.setExtent(farm_extent)
            index_map.setScale(350000)

            index_map.setFrameEnabled(True)
            index_map.setFrameStrokeColor(QColor(0, 0, 0))
            index_map.setFrameStrokeWidth(QgsLayoutMeasurement(0.5, QgsUnitTypes.LayoutMillimeters))
            index_map.setBackgroundEnabled(True)
            index_map.setBackgroundColor(QColor(255, 255, 255))
            index_map.setKeepLayerSet(True)
            index_map.setKeepLayerStyles(True)

            layout.addLayoutItem(index_map)
            index_map.refresh()

            return index_map

        add_mapIndex()

        # GERMINATION SUMMARY TABLE (image) + LEGEND, placed side by side below
        # the main map: table left-aligned, legend to the right of it.
        germination_x, germination_y = 2.366, 450.0
        legend_gap = 2.0
        legend_width_mm = 110.0
        # Right edge lines up with the main map's right edge (2.366 + 836.034)
        germination_w = (2.366 + 836.034) - germination_x - legend_gap - legend_width_mm
        map_bottom_edge = 2.412 + 445.5

        this_page_germination_img_path = germination_img_path
        # Page 2's simple summary table is rendered at its own natural
        # (content-tidy) size, scaled to page 1's mm-per-inch rate, instead of
        # being stretched to fill germination_w — the Legend/Land Application
        # Status blocks are then positioned right after its actual width.
        page2_scale_mm_per_inch = None
        page2_table_dpi = 150
        if is_land_status_page:
            this_page_germination_img_path = germination_img_path_page2
            page2_scale_mm_per_inch = germination_w / FULL_TABLE_FIG_W_INCHES

        # Where the table's own visible top border actually falls (matplotlib's
        # savefig leaves some blank top padding, so this isn't exactly germination_y).
        # On page 2 (no table), push this down: PAGE2_GAP_BELOW_MAP clears space
        # between the main map and the info frame, and the extra 10.0 (matching
        # add_infoFrame's own top_padding) clears space between the frame's top
        # border and the legend content, so neither ends up flush/overlapping.
        PAGE2_GAP_BELOW_MAP = 4.0  # matches page 1's typical map-to-frame gap
        table_border_y = (map_bottom_edge + PAGE2_GAP_BELOW_MAP + 10.0) if is_land_status_page else germination_y
        # Tracks the lowest bottom edge / rightmost edge among the germination
        # table/legend images, so the bounding frame below can be sized to
        # enclose everything (and, on page 2, no more than that).
        content_bottom_y = table_border_y
        content_right_x = germination_x

        def add_germinationTable():
            nonlocal table_border_y, content_bottom_y, content_right_x
            if not os.path.isfile(this_page_germination_img_path):
                return None

            qimg = QImage(this_page_germination_img_path)
            if is_land_status_page:
                render_w = (qimg.width() / page2_table_dpi) * page2_scale_mm_per_inch
                img_height_mm = (qimg.height() / page2_table_dpi) * page2_scale_mm_per_inch
            else:
                aspect = (qimg.height() / qimg.width()) if qimg.width() > 0 else 0.3
                render_w = germination_w
                img_height_mm = render_w * aspect

            top_margin_fraction = _top_content_margin_fraction(this_page_germination_img_path)
            table_border_y = germination_y + (top_margin_fraction * img_height_mm)
            content_bottom_y = max(content_bottom_y, germination_y + img_height_mm)
            content_right_x = max(content_right_x, germination_x + render_w)

            germination_pic = QgsLayoutItemPicture(layout)
            germination_pic.setPicturePath(this_page_germination_img_path)
            germination_pic.attemptMove(QgsLayoutPoint(germination_x, germination_y, QgsUnitTypes.LayoutMillimeters), page=page_index)
            germination_pic.attemptResize(QgsLayoutSize(render_w, img_height_mm, QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(germination_pic)

            return germination_pic

        # Page 2 has no value table — the Legend/Land Application Status
        # blocks start right from the left edge instead.
        if not is_land_status_page:
            add_germinationTable()

        # LEGEND (image only, no border box), to the right of the value table.
        # On page 2 (no table), this starts right at the left edge instead.
        legend_x = content_right_x + legend_gap if is_land_status_page else germination_x + germination_w + legend_gap
        legend_bottom_y = table_border_y

        def add_legendImage():
            nonlocal content_bottom_y, content_right_x, legend_bottom_y
            legend_img_path = os.path.join(img_dir, "legend_p2.png") if is_land_status_page else os.path.join(img_dir, "legend.png")
            if not os.path.isfile(legend_img_path):
                return None

            qimg = QImage(legend_img_path)
            aspect = (qimg.height() / qimg.width()) if qimg.width() > 0 else 0.5

            legend_w = legend_width_mm
            legend_height_mm = legend_w * aspect

            # Cap the legend's height to whatever vertical space remains on the
            # page below the tables, shrinking width (keeping aspect) if needed —
            # otherwise a tall legend (many categories) can run off the bottom edge.
            bottom_margin = 5.0
            max_legend_h = 594.0 - table_border_y - bottom_margin
            if legend_height_mm > max_legend_h:
                legend_height_mm = max_legend_h
                legend_w = legend_height_mm / aspect

            # Align the legend's own visible content (the "Legend" title) with the
            # classification table's visible top border — both images have their
            # own blank top padding from matplotlib, so shift up by the legend
            # image's own margin to cancel it out.
            legend_top_margin_fraction = _top_content_margin_fraction(legend_img_path)
            legend_y = table_border_y - (legend_top_margin_fraction * legend_height_mm)
            content_bottom_y = max(content_bottom_y, legend_y + legend_height_mm)
            content_right_x = max(content_right_x, legend_x + legend_w)
            legend_bottom_y = legend_y + legend_height_mm

            legend_pic = QgsLayoutItemPicture(layout)
            legend_pic.setPicturePath(legend_img_path)
            legend_pic.attemptMove(QgsLayoutPoint(legend_x, legend_y, QgsUnitTypes.LayoutMillimeters), page=page_index)
            legend_pic.attemptResize(QgsLayoutSize(legend_w, legend_height_mm, QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(legend_pic)

            return legend_pic

        add_legendImage()

        # LAND STATUS legend (page 2 only): a separate, dedicated block to
        # the right of the base legend (Next Target/Seed Production/Soil
        # Rehabilitation/D-1.../D-3), showing only the categories actually
        # present for this PID.
        def add_landStatusLegendImage():
            nonlocal content_bottom_y, content_right_x
            if not is_land_status_page or not land_status_legend_img_path:
                return None
            if not os.path.isfile(land_status_legend_img_path):
                return None

            inter_legend_gap = 5.0
            land_status_x = content_right_x + inter_legend_gap

            qimg = QImage(land_status_legend_img_path)

            # Fixed physical scale (not a target width) — swatch/text size
            # stays exactly the same regardless of PID or column count; only
            # the block's overall width/height grows or shrinks with content.
            land_status_w = (qimg.width() / LAND_STATUS_LEGEND_DPI) * LAND_STATUS_LEGEND_SCALE_MM_PER_INCH
            land_status_h = (qimg.height() / LAND_STATUS_LEGEND_DPI) * LAND_STATUS_LEGEND_SCALE_MM_PER_INCH

            # Safety net only — shouldn't normally trigger, since the scale
            # above is already sized to fit a full 8-row column.
            bottom_margin = 5.0
            max_h = 594.0 - table_border_y - bottom_margin
            if land_status_h > max_h:
                scale_down = max_h / land_status_h
                land_status_h *= scale_down
                land_status_w *= scale_down

            top_margin_fraction = _top_content_margin_fraction(land_status_legend_img_path)
            land_status_y = table_border_y - (top_margin_fraction * land_status_h)
            content_bottom_y = max(content_bottom_y, land_status_y + land_status_h)
            content_right_x = max(content_right_x, land_status_x + land_status_w)

            land_status_pic = QgsLayoutItemPicture(layout)
            land_status_pic.setPicturePath(land_status_legend_img_path)
            land_status_pic.attemptMove(QgsLayoutPoint(land_status_x, land_status_y, QgsUnitTypes.LayoutMillimeters), page=page_index)
            land_status_pic.attemptResize(QgsLayoutSize(land_status_w, land_status_h, QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(land_status_pic)

            return land_status_pic

        add_landStatusLegendImage()

        # BOUNDING FRAME: a black-bordered box enclosing the table summary,
        # classification remarks, and legend below the main map. Same extent
        # on both pages — always spans the main map's width.
        def add_infoFrame():
            top_padding = 10.0
            bottom_padding = 1.5
            frame_x = 2.366  # matches the main map's left edge
            frame_w = 836.034  # matches the main map's width
            frame_y = table_border_y - top_padding
            # Never let the frame creep up into the main map above it — keeps
            # the same visual gap between map and frame regardless of how
            # short the table content is.
            frame_y = max(frame_y, map_bottom_edge + 2.0)
            frame_h = (content_bottom_y + bottom_padding) - frame_y

            frame_shape = QgsLayoutItemShape(layout)
            frame_shape.setShapeType(QgsLayoutItemShape.Shape.Rectangle)
            frame_shape.attemptMove(QgsLayoutPoint(frame_x, frame_y, QgsUnitTypes.LayoutMillimeters), page=page_index)
            frame_shape.attemptResize(QgsLayoutSize(frame_w, frame_h, QgsUnitTypes.LayoutMillimeters))

            simple_fill = QgsSimpleFillSymbolLayer()
            simple_fill.setBrushStyle(Qt.BrushStyle.NoBrush)
            simple_fill.setStrokeColor(QColor(0, 0, 0))
            simple_fill.setStrokeWidth(0.5)
            fill_symbol = QgsFillSymbol()
            fill_symbol.changeSymbolLayer(0, simple_fill)
            frame_shape.setSymbol(fill_symbol)
            layout.addLayoutItem(frame_shape)

            return frame_shape

        add_infoFrame()

        return map_item

    # Page 1: the full report. Page 2: currently a complete duplicate — which
    # specific layers get swapped for land_status / soil_rehabilitation will
    # be decided in a later step.
    build_report_page(0)
    build_report_page(1)

    exporter = QgsLayoutExporter(layout)

    # ── Create directory first ───────────────────────────────────────────────────
    output_dir = os.path.join(map_path, run_day_ymd)
    os.makedirs(output_dir, exist_ok=True)

    # ── Then build the full file path ────────────────────────────────────────────
    output_basename = f"{pid}_Gap Detection Map"

    if 'pdf' in EXPORT_FORMATS:
        output_pdf = os.path.join(output_dir, f"{output_basename}.pdf")
        result = exporter.exportToPdf(
            output_pdf,
            QgsLayoutExporter.PdfExportSettings()
        )
        print("PDF export result:", result)
        if result == QgsLayoutExporter.Success:
            print("PDF successfully exported!")
            print(output_pdf)
        else:
            print("PDF export FAILED")

    if 'jpg' in EXPORT_FORMATS:
        output_jpg = os.path.join(output_dir, f"{output_basename}.jpg")
        image_settings = QgsLayoutExporter.ImageExportSettings()
        image_settings.dpi = 300
        # JPEG doesn't support GDAL update access, which world-file/georeferencing
        # writing needs, so disable it to avoid "ERROR 6: ... update access" noise.
        image_settings.generateWorldFile = False
        result = exporter.exportToImage(
            output_jpg,
            image_settings
        )
        print("JPG export result:", result)
        if result == QgsLayoutExporter.Success:
            print("JPG successfully exported!")
            print(output_jpg)
        else:
            print("JPG export FAILED")


def main():
    QgsApplication.setPrefixPath(qgis_apps, True)
    app = QgsApplication([], False)
    app.initQgis()
    try:
        companies_select = c2

        log_dir = os.path.join(project_root, 'pid_error_logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'pid_error_log_{run_day_ymd}.txt')

        # Build the paddock CU/CP-per-PID layers once for this company run,
        # instead of re-filtering/merging them on every PID iteration.
        gdb_path    = cfg['companies'][companies_select]['gdb_path']
        land_status_path = cfg['companies'][companies_select]['land_status_path']
        soil_rehab_path  = cfg['companies'][companies_select]['soil_rehabilitation_path']
        paddock_gdf = gpd.read_file(gdb_path, layer='paddock')

        # Soil Rehabilitation features, read once — clipped per PID below to
        # compute the page 2 summary table's Soil Rehabilitation (Ha) value.
        soil_rehab_gdf = gpd.read_file(soil_rehab_path, layer='soil_rehabilitation')

        # Land Status categories, pulled directly from landstatusStyle.qml's
        # categorized renderer (value -> (label, hex color)) — used to build
        # a per-PID page 2 legend showing only the categories actually
        # present for that PID, with their real symbology, instead of a
        # hand-made generic swatch.
        land_status_layer_name = fiona.listlayers(land_status_path)[-1]
        land_status_gdf = gpd.read_file(land_status_path, layer=land_status_layer_name)

        land_status_style_layer = QgsVectorLayer(
            f"{land_status_path}|layername={land_status_layer_name}",
            "Land Status Style Reference",
            "ogr"
        )
        land_status_style_layer.loadNamedStyle(os.path.join(qml_dir, "landstatusStyle.qml"))
        land_status_category_map = {}
        land_status_renderer = land_status_style_layer.renderer()
        if land_status_renderer is not None:
            for category in land_status_renderer.categories():
                symbol = category.symbol()
                color_hex = symbol.color().name() if symbol is not None else '#999999'
                land_status_category_map[category.value()] = (category.label(), color_hex)

        paddock_cucp_gdf = paddock_gdf[paddock_gdf['LANDUSETYP'].isin(['CU', 'CP'])]
        paddock_cucp_gdf = paddock_cucp_gdf.dissolve(by='PID', as_index=False)

        paddock_cucp_dir = os.path.join(project_root, 'lib', 'tmp')
        os.makedirs(paddock_cucp_dir, exist_ok=True)

        paddock_cucp_path = os.path.join(paddock_cucp_dir, f'paddock_cucp_{companies_select}.gpkg')
        paddock_cucp_gdf.to_file(paddock_cucp_path, layer='paddock_cucp', driver='GPKG')

        # Build the gap and planting GeoDataFrames once, for the germination
        # summary table images (one image generated per PID below).
        gpkg_gaps_planting_path = cfg['companies'][companies_select]['gpkg_gaps_planting_path']
        fiona_latest_gap = fiona.listlayers(gpkg_gaps_planting_path)[-1]
        gap_gdf = gpd.read_file(gpkg_gaps_planting_path, layer=fiona_latest_gap)
        planting_gdf = gpd.read_file(gdb_path, layer='planting')

        # MNM's paddock layer has no 'CP' (planted) LANDUSETYP at all, so
        # "Next Target" is instead defined as the planting boundary itself
        # (per PID), and its area value as planting area minus what gap
        # detection has already captured for that PID.
        paddock_cp_gdf = planting_gdf.dissolve(by='PID', as_index=False)

        paddock_cp_path = os.path.join(paddock_cucp_dir, f'paddock_cp_{companies_select}.gpkg')
        paddock_cp_gdf.to_file(paddock_cp_path, layer='paddock_cp', driver='GPKG')

        planting_area_by_pid = paddock_cp_gdf.set_index('PID').area / 10000

        # ── Join gap features with the planting database's 'Status' field
        # ('Commercial Plantation' vs 'Seed Production'), matched by
        # PID + variety + planting date, instead of a hardcoded commercial date ──
        gap_original_crs = gap_gdf.crs
        gap_gdf['_join_date'] = pd.to_datetime(gap_gdf['plant_date']).dt.date

        planting_status = planting_gdf[['PID', 'VARIETY', 'DATE', 'Status']].copy()
        planting_status['_join_date'] = pd.to_datetime(planting_status['DATE']).dt.date
        planting_status = planting_status.drop_duplicates(subset=['PID', 'VARIETY', '_join_date'])
        planting_status = planting_status[['PID', 'VARIETY', '_join_date', 'Status']]

        gap_gdf = gap_gdf.merge(
            planting_status,
            left_on=['pid', 'variety', '_join_date'],
            right_on=['PID', 'VARIETY', '_join_date'],
            how='left'
        )
        gap_gdf = gap_gdf.drop(columns=['_join_date', 'PID', 'VARIETY'])
        if not isinstance(gap_gdf, gpd.GeoDataFrame):
            gap_gdf = gpd.GeoDataFrame(gap_gdf, geometry='geometry', crs=gap_original_crs)

        gap_status_path = os.path.join(paddock_cucp_dir, f'gap_status_{companies_select}.gpkg')
        gap_gdf.to_file(gap_status_path, layer='gap_status', driver='GPKG')

        # Commercial-plantings mask, matching whatever filter gap_layer/seed_layer
        # use on the map (see COMMERCIAL_FILTER_MODE at the top of this file).
        if COMMERCIAL_FILTER_MODE == 'date':
            commercial_mask = pd.to_datetime(gap_gdf['plant_date']) >= pd.to_datetime(COMMERCIAL_DATE_CUTOFF)
        else:
            commercial_mask = gap_gdf['Status'] == COMMERCIAL_STATUS_VALUE

        # "Next Target" value per PID = planting boundary area minus the area
        # gap detection has already captured for commercial plantings there.
        gap_captured_by_pid = (
            gap_gdf[commercial_mask & (gap_gdf['cls'].isin(['plant', 'gaps spot']))]
            .groupby('pid')['cls_area_ha']
            .sum()
        )

        # Run every PID that has at least one commercial-planting feature,
        # instead of the hardcoded debug list.
        pid_list = sorted(gap_gdf[commercial_mask]['pid'].dropna().unique())
        print(f"PIDs to run ({len(pid_list)}): {pid_list}")

        germination_tmp_dir = os.path.join(tempfile.gettempdir(), 'qgis_automation_germination_tables')
        os.makedirs(germination_tmp_dir, exist_ok=True)

        for pid in pid_list:
            try:
                print(f"Running for company: {companies_select}, PID: {pid}")

                planting_area_pid = float(planting_area_by_pid.get(pid, 0.0))
                gap_captured_pid = float(gap_captured_by_pid.get(pid, 0.0))
                next_target_value = max(planting_area_pid - gap_captured_pid, 0.0)

                germination_img_path = os.path.join(germination_tmp_dir, f'germination_table_{pid}.png')
                variety_index_map = create_gap_table_image(
                    pid                     = pid,
                    gap                     = gap_gdf,
                    merge_cucp              = paddock_cucp_gdf,
                    paddok                  = paddock_gdf,
                    planting                = planting_gdf,
                    output_path             = germination_img_path,
                    dpi                     = 150,
                    planted_area_override   = next_target_value,
                    commercial_status_value = COMMERCIAL_STATUS_VALUE,
                    commercial_date_cutoff  = COMMERCIAL_DATE_CUTOFF if COMMERCIAL_FILTER_MODE == 'date' else None
                )

                # Page 2's value table is a simpler summary: Planted area vs.
                # Soil Rehabilitation / Land Application Status areas, each
                # with a completion status relative to the planted area.
                planted_area_ha = planting_area_pid

                pid_boundary_rows = paddock_cucp_gdf.loc[paddock_cucp_gdf['PID'] == pid, 'geometry']
                if not pid_boundary_rows.empty:
                    pid_boundary_geom = pid_boundary_rows.iloc[0]
                    soil_rehab_subset = soil_rehab_gdf[soil_rehab_gdf.intersects(pid_boundary_geom)]
                    soil_rehab_area_ha = soil_rehab_subset.geometry.intersection(pid_boundary_geom).area.sum() / 10000
                else:
                    soil_rehab_area_ha = 0.0

                land_status_area_ha = (
                    land_status_gdf.loc[land_status_gdf['PID'] == pid, 'geometry'].area.sum() / 10000
                )

                germination_img_path_page2 = os.path.join(germination_tmp_dir, f'germination_table_{pid}_page2.png')
                create_land_application_table_image(
                    planted_area_ha      = planted_area_ha,
                    soil_rehab_area_ha   = soil_rehab_area_ha,
                    land_status_area_ha  = land_status_area_ha,
                    output_path          = germination_img_path_page2,
                    dpi                  = 150,
                )

                # Page 2's base Legend is the static img/legend_p2.png (see
                # add_legendImage in build_report_page) plus a separate,
                # dedicated Land Status legend to its right — showing only
                # the categories actually present for this PID, with their
                # real qml colors/labels.
                present_land_status_values = set(
                    land_status_gdf.loc[land_status_gdf['PID'] == pid, 'LAND_STAT'].dropna().unique()
                )
                land_status_items = [
                    land_status_category_map[v]
                    for v in present_land_status_values
                    if v in land_status_category_map
                ]
                # No placeholder when empty — only show this block when the
                # PID actually has Land Status categories rendered on the map.
                land_status_legend_img_path = None
                if land_status_items:
                    land_status_legend_img_path = os.path.join(germination_tmp_dir, f'legend_land_status_{pid}.png')
                    create_land_status_legend_image(
                        output_path        = land_status_legend_img_path,
                        land_status_items  = land_status_items,
                        dpi                = LAND_STATUS_LEGEND_DPI,
                        max_rows_per_col   = LAND_STATUS_LEGEND_MAX_ROWS_PER_COL,
                    )

                run_single_company(companies_select, pid, paddock_cucp_path, paddock_cp_path, gap_status_path, germination_img_path, germination_img_path_page2, land_status_legend_img_path, variety_index_map)
            except Exception as exc:
                error_message = (
                    f"company={companies_select}\n"
                    f"pid={pid}\n"
                    f"error={type(exc).__name__}: {exc}\n"
                    f"traceback:\n{traceback.format_exc()}\n"
                    f"{'=' * 80}\n"
                )
                print(f"PID ERROR for company={companies_select}, pid={pid}: {exc}")
                with open(log_file, 'a', encoding='utf-8') as log:
                    log.write(error_message)
                continue
    finally:
        app.exitQgis()

if __name__ == "__main__":
    main()
