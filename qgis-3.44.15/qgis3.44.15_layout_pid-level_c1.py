from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsPrintLayout,
    QgsLayoutItemMap,
    QgsLayoutItemPage,
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
    QgsLayoutItemShape,
    QgsSimpleFillSymbolLayer,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsPalLayerSettings,
    QgsVectorLayerSimpleLabeling,
    QgsTextFormat,
    QgsProperty,
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
from datetime import date
import os
import pyogrio
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

from germination_table_img import create_gap_table_image, create_farm_growth_class_table_image
from planting_handler import planting_handler
from legend_img import GROWTH_CLASSES, create_growth_classification_legend_image

qml_dir = os.path.join(project_root, 'qml')
img_dir = os.path.join(project_root, 'img')

# ── CONFIGURATION ──────────────────────────────────────────────────────────────
configuration_variable_path = os.path.join(project_root, 'config.yaml')
with open(configuration_variable_path, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

qgis_apps           = cfg['qgis_apps']
c1                  = cfg['companies_alias']['c1']

today = date.today()
run_day = today.strftime("%d %B %Y")
run_day_ymd = today.strftime("%Y%m%d")

# ── Export formats: any combination of 'pdf', 'jpg' ────────────────────────────
# PDF holds both pages in one file; JPG writes one file per page (<name>_2.jpg).
EXPORT_FORMATS = ['pdf']

COMMERCIAL_STATUS = 'Commercial Plantation'
SEED_STATUS       = 'Seed Production'

# ── A1 landscape page geometry (mm) ────────────────────────────────────────────
PAGE_W, PAGE_H = 841.0, 594.0
MAP_X, MAP_Y   = 2.366, 2.412
MAP_W, MAP_H   = 836.034, 445.5

# Bottom info panel (legend + table) below the main map, down to the page margin
PANEL_Y = MAP_Y + MAP_H + 3.0
PANEL_H = (PAGE_H - MAP_Y) - PANEL_Y
PANEL_PAD_TOP = 10.0
PANEL_PAD_BOTTOM = 5.0

LEGEND_X = MAP_X + 7.0
TABLE_X  = 158.0
# Table/legend images are rendered at their real size in inches and placed at
# this fixed scale, so text size matches across pages and PIDs.
TABLE_MM_PER_INCH  = 34.0
LEGEND_MM_PER_INCH = 28.0
TABLE_DPI = 150
# Page 1 table is scaled up to fill the bottom panel, so render it sharper
GAP_TABLE_DPI = 300
# Share of the panel's free width/height the page 1 table fills (1.0 = all)
GAP_TABLE_FILL = 0.8


def _trim_white_margins(image_path, threshold=200, pad=4):
    """Save a copy of image_path cropped to its visible (non-white) content,
    plus `pad` px. Returns (trimmed_path, original (w, h) px, trimmed (w, h) px).

    Legend images carry a tall opaque white margin; placed untrimmed, that
    margin paints over the main map's bottom frame line."""
    img = PILImage.open(image_path).convert('RGB')
    arr = np.array(img.convert('L'))
    ys, xs = np.nonzero(arr < threshold)
    if len(xs) == 0:
        return image_path, img.size, img.size
    box = (max(xs.min() - pad, 0), max(ys.min() - pad, 0),
           min(xs.max() + pad + 1, img.width), min(ys.max() + pad + 1, img.height))
    trimmed = img.crop(box)
    trimmed_dir = os.path.join(tempfile.gettempdir(), 'qgis_automation_pid_tables')
    os.makedirs(trimmed_dir, exist_ok=True)
    trimmed_path = os.path.join(trimmed_dir, f"{Path(image_path).stem}_trimmed.png")
    trimmed.save(trimmed_path)
    return trimmed_path, img.size, trimmed.size


def _growth_class(growth_pct):
    """GROWTH_CLASSES label for a growth percentage (None if not computable)."""
    if growth_pct is None or not math.isfinite(growth_pct):
        return None
    for label, lower, upper, _ in GROWTH_CLASSES:
        if (lower is None or growth_pct >= lower) and (upper is None or growth_pct < upper):
            return label
    return None


def _layer_extent(layer):
    """Extent of a subset-filtered layer, computed from its features
    (layer.extent() can ignore the subset on a GPKG with an rtree index)."""
    extent = QgsRectangle()
    for feature in layer.getFeatures():
        geom = feature.geometry()
        if geom is not None and not geom.isEmpty():
            extent.combineExtentWith(geom.boundingBox())
    return extent


def run_single_pid(companies_select, pid, paddock_cucp_path, paddock_cp_path, gap_status_path,
                   gap_table_img_path, class_table_img_path, class_legend_img_path,
                   variety_index_map) -> None:
    print('PID: ', pid)

    map_path                    = cfg['companies'][companies_select]['map_path']
    infra_path                  = cfg['companies'][companies_select]['infra_path']
    landuse_path                = cfg['companies'][companies_select]['landuse_path']

    # Ensure project is fresh for each run
    project = QgsProject.instance()
    project.clear()

    # CREATE QGIS PROJECT
    project = QgsProject.instance()
    project.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

    def load_layer(path, layername, name, subset=None):
        layer = QgsVectorLayer(f"{path}|layername={layername}", name, "ogr")
        layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
        if subset:
            layer.setSubsetString(subset)
        return layer

    escaped_pid       = pid.replace("'", "''")
    pid_filter_gap    = f"\"pid\" = '{escaped_pid}'"
    pid_filter_paddock = f"\"PID\" = '{escaped_pid}'"

    ## Page 1 — Gap Database, Commercial Plantation features: growth vs gap
    gap_layer = load_layer(gap_status_path, 'gap_status', 'Gap Detection',
                           f"{pid_filter_gap} AND \"Status\" = '{COMMERCIAL_STATUS}'")
    gap_layer.loadNamedStyle(os.path.join(qml_dir, "gapsAreaStyle.qml"))
    ## Label each gap feature with the same "(N)" index shown next to its
    ## variety's planting period in the page 1 table. Must be set AFTER
    ## loadNamedStyle(), which resets labeling.
    if variety_index_map:
        map_pairs = ",".join(
            f"'{str(var).replace(chr(39), chr(39) * 2)}',{idx}"
            for var, idx in variety_index_map.items()
        )
        pal_settings = QgsPalLayerSettings()
        pal_settings.fieldName = f"'(' || map_get(map({map_pairs}), \"variety\") || ')'"
        pal_settings.isExpression = True
        text_format = QgsTextFormat()
        text_format.setSize(15)
        pal_settings.setFormat(text_format)
        gap_layer.setLabeling(QgsVectorLayerSimpleLabeling(pal_settings))
        gap_layer.setLabelsEnabled(True)
    project.addMapLayer(gap_layer)

    ## Page 1 — Seed Production features, single orange fill
    seed_layer = load_layer(gap_status_path, 'gap_status', 'Seed',
                            f"{pid_filter_gap} AND \"Status\" = '{SEED_STATUS}'")
    seed_layer.renderer().setSymbol(QgsFillSymbol.createSimple({
        "color": "#ffc986",
        "outline_style": "no",
    }))
    project.addMapLayer(seed_layer)

    ## Page 1 — Paddock CP (Next Target)
    paddock_cp_layer = load_layer(paddock_cp_path, 'paddock_cp', 'Paddock CP', pid_filter_paddock)
    paddock_cp_layer.renderer().setSymbol(QgsFillSymbol.createSimple({
        "color": "#e2ff9f",
        "outline_style": "no",
    }))
    project.addMapLayer(paddock_cp_layer)

    ## Page 2 — Commercial Plantation features coloured by their
    ## cluster_planting's growth classification (growth_class, built in main())
    class_layer = load_layer(gap_status_path, 'gap_status', 'Growth Classification',
                             f"{pid_filter_gap} AND \"Status\" = '{COMMERCIAL_STATUS}'")
    class_categories = []
    for label, _, _, color in GROWTH_CLASSES:
        symbol = QgsFillSymbol.createSimple({"color": color, "outline_style": "no"})
        class_categories.append(QgsRendererCategory(label, symbol, label))
    class_layer.setRenderer(QgsCategorizedSymbolRenderer('growth_class', class_categories))
    project.addMapLayer(class_layer)

    ## Shared by both pages — the selected PID's boundary (bold, no fill)
    paddock_selected_layer = load_layer(paddock_cucp_path, 'paddock_cucp', 'Selected PID', pid_filter_paddock)
    paddock_selected_layer.loadNamedStyle(os.path.join(qml_dir, "selectedPIDStyle.qml"))
    project.addMapLayer(paddock_selected_layer)

    ## Shared by both pages — every paddock's CU/CP boundary, but only the
    ## selected PID gets its label
    paddock_cucp_layer = load_layer(paddock_cucp_path, 'paddock_cucp', 'Paddock CUCP')
    paddock_cucp_layer.loadNamedStyle(os.path.join(qml_dir, "cucpStyle.qml"))
    cucp_labeling = paddock_cucp_layer.labeling()
    if cucp_labeling is not None:
        cucp_pal_settings = cucp_labeling.settings()
        cucp_pal_settings.dataDefinedProperties().setProperty(
            QgsPalLayerSettings.Property.Show,
            QgsProperty.fromExpression(pid_filter_paddock)
        )
        paddock_cucp_layer.setLabeling(QgsVectorLayerSimpleLabeling(cucp_pal_settings))
    project.addMapLayer(paddock_cucp_layer)

    road_layer = load_layer(infra_path, 'road', 'Road')
    road_layer.loadNamedStyle(os.path.join(qml_dir, "RoadGISStyle.qml"))
    project.addMapLayer(road_layer)

    drainage_layer = load_layer(infra_path, 'drainage', 'Drainage')
    drainage_layer.loadNamedStyle(os.path.join(qml_dir, "drainageStyle.qml"))
    project.addMapLayer(drainage_layer)

    ## Water Body — landuse paddocks with LANDUSETYP = 'WB' (waterBodyStyle.qml
    ## is written against the paddock layer's fields)
    wb_layer = load_layer(landuse_path, 'paddock', 'Water Body', "\"LANDUSETYP\" = 'WB'")
    wb_layer.loadNamedStyle(os.path.join(qml_dir, "waterBodyStyle.qml"))
    project.addMapLayer(wb_layer)

    ## Index map layers — Farm/Block boundaries, this PID in yellow
    farm_index_layer = load_layer(landuse_path, 'Farm', 'Farm Index')
    farm_index_layer.loadNamedStyle(os.path.join(qml_dir, "farmGermStyle.qml"))
    project.addMapLayer(farm_index_layer)

    block_index_layer = load_layer(landuse_path, 'Block', 'Block Index')
    block_index_layer.loadNamedStyle(os.path.join(qml_dir, "blockStyle.qml"))
    project.addMapLayer(block_index_layer)

    index_selected_layer = load_layer(paddock_cucp_path, 'paddock_cucp', 'Selected PID Index', pid_filter_paddock)
    index_selected_layer.renderer().setSymbol(QgsFillSymbol.createSimple({
        "color": "#ffff00",
        "outline_color": "#000000",
        "outline_width": "0.2",
    }))
    project.addMapLayer(index_selected_layer)

    # ── Main map extent: the selected PID's CU/CP boundary ───────────────────
    extent = _layer_extent(paddock_selected_layer)
    extent_valid = not extent.isNull() and extent.width() > 0 and extent.height() > 0 and all(
        math.isfinite(v) for v in (extent.xMinimum(), extent.xMaximum(), extent.yMinimum(), extent.yMaximum())
    )
    if not extent_valid:
        raise ValueError(
            f"PID {pid} has no valid map extent in the paddock CU/CP layer. | "
            f"company={companies_select}, feature_count={paddock_selected_layer.featureCount()}, "
            f"filter={pid_filter_paddock}"
        )
    extent.scale(1.1)  # 10% margin

    # PRODUCE LAYOUTING MANAGER
    manager = project.layoutManager()
    layout_name = "Automation Map"
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(layout_name)
    manager.addLayout(layout)

    # ── TWO A1 LANDSCAPE PAGES ───────────────────────────────────────────────
    page = layout.pageCollection().page(0)
    page.setPageSize(QgsLayoutSize(PAGE_W, PAGE_H, QgsUnitTypes.LayoutMillimeters))
    page2 = QgsLayoutItemPage(layout)
    page2.setPageSize(QgsLayoutSize(PAGE_W, PAGE_H, QgsUnitTypes.LayoutMillimeters))
    layout.pageCollection().addPage(page2)

    def add_mainMap(page_index, layers):
        map_item = QgsLayoutItemMap(layout)
        map_item.setLayers(layers)
        map_item.attemptMove(QgsLayoutPoint(MAP_X, MAP_Y, QgsUnitTypes.LayoutMillimeters), page=page_index)
        map_item.attemptResize(QgsLayoutSize(MAP_W, MAP_H, QgsUnitTypes.LayoutMillimeters))
        map_item.zoomToExtent(extent)

        # Round up scale
        current_scale = map_item.scale()
        if not math.isfinite(current_scale) or current_scale <= 0:
            raise ValueError(f"PID {pid} produced an invalid map scale ({current_scale}) after zooming to extent.")
        map_item.setScale(math.ceil(current_scale / 1000) * 1000)

        map_item.setFrameEnabled(True)
        map_item.setFrameStrokeColor(QColor(0, 0, 0))
        map_item.setFrameStrokeWidth(QgsLayoutMeasurement(0.5, QgsUnitTypes.LayoutMillimeters))
        map_item.setKeepLayerSet(True)
        map_item.setKeepLayerStyles(True)
        layout.addLayoutItem(map_item)
        map_item.refresh()
        return map_item

    # MAP INDEX (overlay inset in the main map's bottom-left corner)
    def add_mapIndex(page_index):
        index_map = QgsLayoutItemMap(layout)
        index_map.setLayers([index_selected_layer, block_index_layer, farm_index_layer])

        # Match the frame's aspect ratio to the whole Farm layer's extent, so
        # the content fills the frame edge-to-edge with no letterbox gap.
        farm_extent = farm_index_layer.extent()
        farm_aspect = farm_extent.width() / farm_extent.height()
        index_w = 90.0 * 1.3
        index_h = index_w / farm_aspect

        margin = 5.0
        index_x = MAP_X + margin
        index_y = MAP_Y + MAP_H - margin - index_h
        index_map.attemptMove(QgsLayoutPoint(index_x, index_y, QgsUnitTypes.LayoutMillimeters), page=page_index)
        index_map.attemptResize(QgsLayoutSize(index_w, index_h, QgsUnitTypes.LayoutMillimeters))
        index_map.setExtent(farm_extent)
        # Zoom out 20% around the same center, so the farms don't touch the frame
        index_map.setScale(index_map.scale() * 1.2)

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

    # BOTTOM PANEL: legend (left) + table (right) inside one bordered frame
    def add_infoPanel(page_index, legend_img_path, legend_mm_per_px, table_img_path, fit_table=False):
        table_y = PANEL_Y + PANEL_PAD_TOP
        max_h   = (PANEL_Y + PANEL_H - PANEL_PAD_BOTTOM) - table_y

        ## Table, trimmed to its border. Placed at the fixed TABLE_MM_PER_INCH
        ## scale (shrunk only if it would run past the frame), or with
        ## fit_table=True scaled up to fill the panel's free width/height.
        table_trimmed_path, _, (table_w_px, table_h_px) = _trim_white_margins(table_img_path)
        table_w = table_w_px / TABLE_DPI * TABLE_MM_PER_INCH
        table_h = table_h_px / TABLE_DPI * TABLE_MM_PER_INCH
        max_w = (MAP_X + MAP_W - 5.0) - TABLE_X
        shrink = min(max_h / table_h, max_w / table_w)
        if fit_table:
            shrink *= GAP_TABLE_FILL
        else:
            shrink = min(1.0, shrink)
        table_w, table_h = table_w * shrink, table_h * shrink

        table_pic = QgsLayoutItemPicture(layout)
        table_pic.setPicturePath(table_trimmed_path)
        table_pic.attemptMove(QgsLayoutPoint(TABLE_X, table_y, QgsUnitTypes.LayoutMillimeters), page=page_index)
        table_pic.attemptResize(QgsLayoutSize(table_w, table_h, QgsUnitTypes.LayoutMillimeters))
        layout.addLayoutItem(table_pic)

        ## Legend, trimmed to its content so its top (the title) sits at the
        ## table's top border
        trimmed_path, _, (trim_w_px, trim_h_px) = _trim_white_margins(legend_img_path)
        legend_w, legend_h = trim_w_px * legend_mm_per_px, trim_h_px * legend_mm_per_px
        legend_pic = QgsLayoutItemPicture(layout)
        legend_pic.setPicturePath(trimmed_path)
        legend_pic.attemptMove(QgsLayoutPoint(LEGEND_X, table_y, QgsUnitTypes.LayoutMillimeters), page=page_index)
        legend_pic.attemptResize(QgsLayoutSize(legend_w, legend_h, QgsUnitTypes.LayoutMillimeters))
        layout.addLayoutItem(legend_pic)

        ## Frame
        frame_shape = QgsLayoutItemShape(layout)
        frame_shape.setShapeType(QgsLayoutItemShape.Shape.Rectangle)
        frame_shape.attemptMove(QgsLayoutPoint(MAP_X, PANEL_Y, QgsUnitTypes.LayoutMillimeters), page=page_index)
        frame_shape.attemptResize(QgsLayoutSize(MAP_W, PANEL_H, QgsUnitTypes.LayoutMillimeters))
        simple_fill = QgsSimpleFillSymbolLayer()
        simple_fill.setBrushStyle(Qt.BrushStyle.NoBrush)
        simple_fill.setStrokeColor(QColor(0, 0, 0))
        simple_fill.setStrokeWidth(0.5)
        fill_symbol = QgsFillSymbol()
        fill_symbol.changeSymbolLayer(0, simple_fill)
        frame_shape.setSymbol(fill_symbol)
        layout.addLayoutItem(frame_shape)

    # ── PAGE 1: Growth & Gap ─────────────────────────────────────────────────
    # Draw order (first = topmost). Boundaries (transparent fill) sit above
    # drainage; paddock_cp_layer (Next Target) sits under gap/seed so only
    # not-yet-analysed CP areas show its fill.
    add_mainMap(0, [road_layer, paddock_selected_layer, paddock_cucp_layer, drainage_layer,
                    gap_layer, seed_layer, paddock_cp_layer, wb_layer])
    add_mapIndex(0)
    # Static legend.png: scaled so the full (untrimmed) image would be 145 mm wide
    base_legend_path = os.path.join(img_dir, "legend.png")
    # The table is enlarged to fill the panel, so it's rendered at
    # GAP_TABLE_DPI to stay sharp.
    add_infoPanel(0, base_legend_path, 145.0 / QImage(base_legend_path).width(),
                  gap_table_img_path, fit_table=True)

    # ── PAGE 2: Growth Classification by cluster_planting ────────────────────
    add_mainMap(1, [road_layer, paddock_selected_layer, paddock_cucp_layer, drainage_layer,
                    class_layer, wb_layer])
    add_mapIndex(1)
    add_infoPanel(1, class_legend_img_path, LEGEND_MM_PER_INCH / TABLE_DPI,
                  class_table_img_path)

    exporter = QgsLayoutExporter(layout)

    # ── Create directory first ───────────────────────────────────────────────────
    output_dir = os.path.join(map_path, f"pid_{run_day_ymd}")
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


def build_class_rows(pid, cluster_summary):
    """Page 2 table rows: analysed area (Ha) and share (%) per growth class."""
    pid_clusters = cluster_summary[cluster_summary['pid'] == pid]
    total = pid_clusters['analysed_ha'].sum()
    rows = []
    for label, _, _, _ in GROWTH_CLASSES:
        area = pid_clusters[pid_clusters['growth_class'] == label]['analysed_ha'].sum()
        rows.append((label, area, (area / total * 100) if total > 0 else 0.0))
    return rows


def main():
    QgsApplication.setPrefixPath(qgis_apps, True)
    app = QgsApplication([], False)
    app.initQgis()
    try:
        companies_select = c1

        log_dir = os.path.join(project_root, 'pid_error_logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'pid_error_log_{run_day_ymd}.txt')

        # Build the paddock CU/CP layers once for this company run
        landuse_path = cfg['companies'][companies_select]['landuse_path']
        paddock_gdf = gpd.read_file(landuse_path, layer='paddock')

        paddock_cucp_gdf = paddock_gdf[paddock_gdf['LANDUSETYP'].isin(['CU', 'CP'])]
        paddock_cucp_gdf = paddock_cucp_gdf.dissolve(by='PID', as_index=False)

        paddock_cp_gdf = paddock_gdf[paddock_gdf['LANDUSETYP'] == 'CP']
        paddock_cp_gdf = paddock_cp_gdf.dissolve(by='PID', as_index=False)

        tmp_dir = os.path.join(project_root, 'lib', 'tmp')
        os.makedirs(tmp_dir, exist_ok=True)

        paddock_cucp_path = os.path.join(tmp_dir, f'paddock_cucp_{companies_select}.gpkg')
        paddock_cucp_gdf.to_file(paddock_cucp_path, layer='paddock_cucp', driver='GPKG')

        paddock_cp_path = os.path.join(tmp_dir, f'paddock_cp_{companies_select}.gpkg')
        paddock_cp_gdf.to_file(paddock_cp_path, layer='paddock_cp', driver='GPKG')

        gpkg_gaps_planting_path = cfg['companies'][companies_select]['gpkg_gaps_planting_path']
        planting_path           = cfg['companies'][companies_select]['planting_path']
        latest_gap_layer = pyogrio.list_layers(gpkg_gaps_planting_path)[-1][0]
        print(f"Gap layer: {latest_gap_layer}")
        gap_gdf = gpd.read_file(gpkg_gaps_planting_path, layer=latest_gap_layer)
        planting_gdf = planting_handler(planting_path)

        # ── Join gap features with the planting database's 'Status' field
        # ('Commercial Plantation' vs 'Seed Production'), matched by
        # PID + variety + planting date ──
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

        # ── Growth % per cluster_planting = plant / (plant + gap) area, then
        # binned into GROWTH_CLASSES; written onto every feature of the cluster
        # so page 2 can colour the features by their cluster's class ──
        cluster_summary = (
            gap_gdf.assign(plant_ha=gap_gdf['cls_area_ha'].where(gap_gdf['cls'] == 'plant', 0.0))
            .groupby('cluster_planting')
            .agg(pid=('pid', 'first'), status=('Status', 'first'),
                 plant_ha=('plant_ha', 'sum'), analysed_ha=('cls_area_ha', 'sum'))
            .reset_index()
        )
        cluster_summary['growth_pct'] = np.where(
            cluster_summary['analysed_ha'] > 0,
            cluster_summary['plant_ha'] / cluster_summary['analysed_ha'] * 100,
            np.nan
        )
        cluster_summary['growth_class'] = cluster_summary['growth_pct'].map(_growth_class)
        gap_gdf = gap_gdf.merge(
            cluster_summary[['cluster_planting', 'growth_pct', 'growth_class']],
            on='cluster_planting', how='left'
        )
        commercial_clusters = cluster_summary[cluster_summary['status'] == COMMERCIAL_STATUS]

        gap_status_path = os.path.join(tmp_dir, f'gap_status_{companies_select}.gpkg')
        gap_gdf.to_file(gap_status_path, layer='gap_status', driver='GPKG')

        # Run every PID that has at least one 'Commercial Plantation' feature
        pid_list = sorted(gap_gdf[gap_gdf['Status'] == COMMERCIAL_STATUS]['pid'].dropna().unique())
        print(f"PIDs to run ({len(pid_list)}): {pid_list}")

        img_tmp_dir = os.path.join(tempfile.gettempdir(), 'qgis_automation_pid_tables')
        os.makedirs(img_tmp_dir, exist_ok=True)

        class_legend_img_path = os.path.join(img_tmp_dir, 'growth_classification_legend.png')
        create_growth_classification_legend_image(class_legend_img_path, dpi=TABLE_DPI)

        for pid in pid_list:
            try:
                print(f"Running for company: {companies_select}, PID: {pid}")

                ## Page 1 table: one row per variety, its planting period
                ## prefixed with the (N) index that labels its features on the map
                gap_table_img_path = os.path.join(img_tmp_dir, f'gap_table_{pid}.png')
                variety_index_map = create_gap_table_image(
                    pid                           = pid,
                    gap                           = gap_gdf,
                    merge_cucp                    = paddock_cucp_gdf,
                    paddok                        = paddock_gdf,
                    planting                      = planting_gdf,
                    output_path                   = gap_table_img_path,
                    dpi                           = GAP_TABLE_DPI,
                    commercial_status_value       = COMMERCIAL_STATUS,
                    include_classification        = False,
                    include_classification_column = False,
                )

                class_table_img_path = os.path.join(img_tmp_dir, f'class_table_{pid}.png')
                create_farm_growth_class_table_image(
                    farm               = pid,
                    class_rows         = build_class_rows(pid, commercial_clusters),
                    output_path        = class_table_img_path,
                    dpi                = TABLE_DPI,
                    first_col_header   = 'PID',
                    first_col_width_in = 1.55,
                )

                run_single_pid(companies_select, pid, paddock_cucp_path, paddock_cp_path, gap_status_path,
                               gap_table_img_path, class_table_img_path, class_legend_img_path,
                               variety_index_map)
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
