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
    QgsRasterLayer, 
    QgsLayoutItemShape, 
    QgsLayoutPoint,
    QgsSimpleFillSymbolLayer, 
    QgsFillSymbol, 
    QgsLayoutItemMapGrid, 
    QgsTextFormat, 
    QgsLayoutItemPolyline, 
    QgsLineSymbol, 
    QgsLayoutItemLabel, 
    QgsLayoutItemPicture, 
    QgsLayoutItemScaleBar,
    QgsRectangle,
    QgsLayoutMeasurement,
    QgsRuleBasedRenderer,
    QgsSymbol,
    QgsRendererCategory,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsCategorizedSymbolRenderer,
    QgsStyle,
    QgsStyleProxyModel,
    QgsLayoutItemLegend,
    QgsLegendStyle,
    QgsLayerTree
    )

from qgis.PyQt.QtCore import (
    Qt,
    QRectF,
    QPointF
)

from qgis.PyQt.QtGui import (
    QColor,
    QFont,
    QImage,
    QPolygonF
)

import geopandas as gpd
import pandas
from datetime import date, datetime
import os
from osgeo import ogr
import fiona
import yaml

CONFIG_VARIABLES = r"D:\00. Geo-AI Apps\automation of gap and weed detection\variables\qgis_layout_configuration.yaml"

# ── CONFIGURATION ──────────────────────────────────────────────────────────────
configuration_variable_path = CONFIG_VARIABLES
with open(configuration_variable_path, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

companies_select = 'GPA'
gdb_path              = cfg['companies'][companies_select]['gdb_path']
gpkg_gaps_path        = cfg['companies'][companies_select]['gpkg_gaps_path']

today = str(date.today())
today_date = datetime.strptime(today, "%Y-%m-%d")

## Get the Parent Directory
script_dir  = os.path.dirname(os.path.abspath(__file__))
parent_dir = 'D:/00. Geo-AI Apps/automation of gap and weed detection/lib/pyqgis/'
print(parent_dir)

vect = gpd.read_file(os.path.join(parent_dir + "/input/vector/LAND_DEVELOPMENT_PROGRESS.shp"))
date_list = list(set(vect['Date']))
date_form = [datetime.strptime(d, "%Y-%m-%d") for d in date_list] # adjust the date format


# Find the date closest to today
# closest_date = min(date_form, key=lambda x: abs((x - today).days))
date_df = pandas.DataFrame({'date': date_list})
date_df['delta_days'] = [today_date-date for date in date_form]
run_days = date_df[date_df['delta_days'] == min(date_df['delta_days'])]['date'][0]
print('Recent Date: ', run_days)

# # 01 - INITIALIZE QGIS APPLICATION
# QgsApplication.setPrefixPath("C:/Program Files/QGIS 3.34.3/apps/qgis", True)
# app = QgsApplication([], True)
# QgsApplication.initQgis()

# 01 - INITIALIZE QGIS APPLICATION
QgsApplication.setPrefixPath(
    r"C:/Program Files/QGIS 3.34.10/apps/qgis",
    True
)

app = QgsApplication([], False)
app.initQgis()

# 02 - CREATE QGIS PROJECT
project = QgsProject.instance()
project.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

# 03 - LOAD ALL NEEDED LAYERS

## 03.02 Vector Layers
### 03.02.02 Planting Block
block_path = os.path.join(parent_dir + "/input/vector/PETAK_LC.shp")
block_layer = QgsVectorLayer(block_path, "Blok Tanam", "ogr")
block_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
### 03.02.03 Gap Geodatabase
fiona_latest_gap = fiona.listlayers(gpkg_gaps_path)[-1]
latest_gap = 'Gaps-Detection_GPA_20260611_AR'
gap_layer = QgsVectorLayer(
    f"{gpkg_gaps_path}|layername={latest_gap}",
    "Gap Detection",
    "ogr"
)
print('latest_gap: ', fiona_latest_gap)
gap_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
### 03.02.04 Gap Geodatabase
gdb_path = r'D:\00. Geo-AI Apps\automation of gap and weed detection\database\GPA\GPA.gdb'


# 04 - PRODUCE LAYOUTING MANAGER
manager = project.layoutManager()
layout_name = "Automation Map"
layout = manager.layoutByName(layout_name)
layout = QgsPrintLayout(project)
layout.initializeDefaults()
layout.setName(layout_name)
manager.addLayout(layout)

# # 04 - PRODUCE LAYOUTING MANAGER
# manager = project.layoutManager()
# layout_name = "Automation Map"

# # Remove old layout safely
# old_layout = manager.layoutByName(layout_name)

# if old_layout is not None:
#     manager.removeLayout(old_layout)

# # Create fresh layout
# layout = QgsPrintLayout(project)
# layout.initializeDefaults()
# layout.setName(layout_name)

# manager.addLayout(layout)

# 05 - ADD BACKGFROUND FRAME
## 05.01 Main Frame
# main_frame = QgsLayoutItemShape(layout)
# main_frame.setShapeType(QgsLayoutItemShape.Shape.Rectangle)
# main_frame.setRect(0,0, 218.028, 207.286)
# main_frame.attemptMove(QgsLayoutPoint(1.333, 1.416, QgsUnitTypes.LayoutMillimeters))
# layout.addLayoutItem(main_frame)

def frame_style(width):
    simple_fill = QgsSimpleFillSymbolLayer()
    fill_symbol = QgsFillSymbol()
    fill_symbol.changeSymbolLayer(0, simple_fill)
    simple_fill.setColor(Qt.GlobalColor.white)
    simple_fill.setStrokeColor(Qt.GlobalColor.black)
    simple_fill.setStrokeWidth(width)
    return fill_symbol

# main_frame.setSymbol(frame_style(width = 0.1))

## 05 Map Frame
def addFrame(x,y,width,height):
    legend_frame = QgsLayoutItemShape(layout)
    legend_frame.setShapeType(QgsLayoutItemShape.Shape.Rectangle)
    legend_frame.setRect(0, 0, width,height)
    legend_frame.attemptMove(QgsLayoutPoint(x,y, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(legend_frame)
    return legend_frame.setSymbol(frame_style(width = 0.1))
### 05.01 Main Map Frame for Side Information Map
addFrame(215.484, 4.515, 76.785, 200.969)
### 05.02 Navigation Info Frame
addFrame(215.484, 26.559, 76.785, 19.239)
### 05.03 Map Index
addFrame(215.484, 162.234, 76.785, 33.077)





## 05.02 Line Frame
def add_lineFrame(x1,y1,x2,y2,width):
    polygon2 = QPolygonF()
    polygon2.append(QPointF(x1,y1))
    polygon2.append(QPointF(x2,y2))
    layoutItemPolyline = QgsLayoutItemPolyline(polygon2, layout)
    line_symbol = QgsLineSymbol()
    line_symbol.setWidth(width)
    layout.addLayoutItem(layoutItemPolyline)
    layoutItemPolyline.setSymbol(line_symbol)

### Title - North/Scale
# add_lineFrame(x1 = 221.003, y1 = 19.158, x2 = 295.1, y2 = 19.158, width = 0.1)
### North/Scale - Legend
# add_lineFrame(x1 = 221.003, y1 = 43.297, x2 = 295.1, y2 = 43.297, width = 0.1)
### Legend - Map index
# add_lineFrame(x1 = 221.003, y1 = 156.588, x2 = 295.1, y2 = 156.588, width = 0.1)
### Map index - Map Source
# add_lineFrame(x1 = 221.003, y1 = 194.438, x2 = 295.1, y2 = 194.438, width = 0.1)


# 06. MAIN MAP SETTING
## 06.01 Setup Frame & Call All Layers
def add_mainMap(block_layer, gap_layer):
    
    # 01. Add Main Map Frame
    map = QgsLayoutItemMap(layout)
    map.setRect(4.434, 4.515, 211.058, 200.969)  # Example values: x, y, width, height
    map.setExtent(gap_layer.extent())
    map.attemptResize(QgsLayoutSize(211.058, 200.969, QgsUnitTypes.LayoutMillimeters)) # width, height
    map.attemptMove(QgsLayoutPoint(4.434, 4.515))
    map.setFrameStrokeWidth(QgsLayoutMeasurement(0.1, QgsUnitTypes.LayoutMillimeters))
    map.setLayers([gap_layer, block_layer])

    # 02. Show Layers
    ## 02.01 Aerial Basemap
    ## 02.03 Planting Block
    block_style_path = os.path.join(parent_dir + "/input/style/Petak_LandClearing_Style.qml")
    block_layer.loadNamedStyle(block_style_path)
    QgsProject.instance().addMapLayer(block_layer)
    ## 02.04 Gap Detection
    gap_layer_style_path = os.path.join(parent_dir + "/input/style/GapsArea_Style.qml")
    gap_layer.loadNamedStyle(gap_layer_style_path)
    QgsProject.instance().addMapLayer(gap_layer)
    

    extent = gap_layer.extent()
    scale = max(extent.width(), extent.height()) # Adjust divisor as needed
    map.setScale(scale) 
    map.setFrameEnabled(True) # to have a map black border
    map.setKeepLayerSet(True)
    map.setKeepLayerStyles(True)

    layout.addLayoutItem(map)
    return map

map_item = add_mainMap(block_layer, gap_layer)

# 07. ADD LEGEND
def addLegend(list_selected_layers):
    # Add Legend Based on Checked Layers
    legend = QgsLayoutItemLegend(layout)
    # Set the title and font style
    legend.setTitle("Legenda")  # Set the title
    font = QgsTextFormat()
    font.setForcedBold(True)
    font.setColor(Qt.GlobalColor.black)
    font.setSize(12)
    legend.rstyle(QgsLegendStyle.Title).setTextFormat(font)

    legend.attemptMove(QgsLayoutPoint(225, 46, QgsUnitTypes.LayoutMillimeters))
    legend.attemptResize(QgsLayoutSize(66.000,21, QgsUnitTypes.LayoutMillimeters))
    legend.setBackgroundEnabled(False)
    legend.setAutoUpdateModel(False)  # This line is important!!

    font = QgsTextFormat()
    font.setForcedBold(True)
    font.setColor(Qt.GlobalColor.black)
    font.setSize(10)
    legend.rstyle(QgsLegendStyle.Subgroup).setTextFormat(font)

    # # SymbolLabel label style
    font = QgsTextFormat()
    font.setForcedBold(False)
    font.setColor(Qt.GlobalColor.black)
    font.setSize(10)
    legend.rstyle(QgsLegendStyle.SymbolLabel).setTextFormat(font)

    # Get the legend model and the root group
    root_group  = project.layerTreeRoot()
    legend_model = legend.model()
    root_legend_group = legend_model.rootGroup()

    # Remove all children from the root legend group
    for child in root_legend_group.children():
        root_legend_group.removeChildNode(child)


    for child in root_group.children():
        if isinstance(child, QgsLayerTreeLayer) and child.layer().name() in list_selected_layers:
            root_legend_group.addChildNode(child.clone())

    # Refresh the legend
    legend.adjustBoxSize()
    layout.addLayoutItem(legend)

addLegend(list_selected_layers = ["Mekanisasi", "Blok Tanam"])

# 08 - MAP TITLE
main_title = QgsLayoutItemLabel(layout)
layout.addLayoutItem(main_title)
main_title.setText("PETA KERJA LAND DEVELOPMENT AUSSIE BILLET")
main_title.setHAlign(Qt.AlignCenter)
main_title.setVAlign(Qt.AlignVCenter)
main_title.attemptResize(QgsLayoutSize(68.838, 18.152, QgsUnitTypes.LayoutMillimeters)) # width, height
main_title.attemptMove(QgsLayoutPoint(223.5, 1.8, QgsUnitTypes.LayoutMillimeters))
main_title_style = QgsTextFormat()
main_title_style.setColor(Qt.GlobalColor.black)
main_title_style.setSize(12)
main_title_style.setForcedBold(True)
main_title.setTextFormat(main_title_style)

# 09 - ADD SCALE BAR
scalebar_item = QgsLayoutItemScaleBar(layout)
scalebar_item.setStyle('Single Box')
scalebar_item.setLinkedMap(map_item)
scalebar_item.setUnits(QgsUnitTypes.DistanceMeters)
scalebar_item.setNumberOfSegments(3)
scalebar_item.applyDefaultSize()
# scalebar_item.setSegmentSizeMode(100)
# scalebar_item.applyDefaultSettings()
# scalebar_item.setNumberOfSegmentsLeft(0)
# scalebar_item.setUnitsPerSegment(150)
scalebar_item.setHeight(1)
scalebar_item.setLabelBarSpace(1.5)
scalebar_item.setUnitLabel('m')
# scalebar_item.setBackgroundEnabled(True)
# scalebar_item.setBackgroundColor(QColor(255, 255, 255, 255))
scalebar_item.update()
scalebar_item.attemptMove(QgsLayoutPoint(237, 32.258))

scalebar_font = QgsTextFormat()
scalebar_font.setFont(QFont('MS Shell Dlg 2', 1))
scalebar_item.setTextFormat(scalebar_font)
layout.addLayoutItem(scalebar_item)

# 10 - ADD NORTH ARROW
picture_item = QgsLayoutItemPicture(layout)
svg_file_path = os.path.join(parent_dir + "/input/svg/simple-wind-rose.svg")
picture_item.setPicturePath(svg_file_path)
# picture_item.setSize(100, 100) 
picture_item.attemptResize(QgsLayoutSize(22.844, 20.942, QgsUnitTypes.LayoutMillimeters)) # width, height
picture_item.attemptMove(QgsLayoutPoint(250.258, 16.5))
layout.addLayoutItem(picture_item)

# 11 - MAP SOURCE INFO
def add_mapSource(layout, date):
    submber_data = QgsLayoutItemLabel(layout)
    submber_data_style = QgsTextFormat()
    submber_data_style.setColor(Qt.GlobalColor.black)
    submber_data_style.setSize(8)
    submber_data.setText(f'Sumber Data:\n' 
                         f'1. Tracking Team Land Preparation {date}\n' 
                         f'2. Foto Udara {date}')
    submber_data.setTextFormat(submber_data_style)

    #set size of label item. this step seems a little pointless to me but it doesn't work without it
    submber_data.adjustSizeToText() 
    submber_data.setMarginX(3)
    submber_data.attemptMove(QgsLayoutPoint(221.5, 196.905, QgsUnitTypes.LayoutMillimeters))
    submber_data.attemptResize(QgsLayoutSize(75.937, 11.287, QgsUnitTypes.LayoutMillimeters)) # width, height

    layout.addLayoutItem(submber_data)

add_mapSource(layout, run_days)

# 12 - MAP INDEX
devArea_path = os.path.join(parent_dir + "/input/vector/Dev_Areas.shp")
devArea_layer = QgsVectorLayer(devArea_path, "Mekanisasi", "ogr")
devArea_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
devArea_style_path = os.path.join(parent_dir + "/input/style/DevArea_Style.qml")
devArea_layer.loadNamedStyle(devArea_style_path)
QgsProject.instance().addMapLayer(devArea_layer)

LD_path = os.path.join(parent_dir + "/input/vector/LAND_DEVELOPMENT_PROGRESS.shp")
LD_index = QgsVectorLayer(LD_path, "Mekanisasi", "ogr")
LD_index.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
LD_index_style_path = os.path.join(parent_dir + "/input/style/objectIndex_Style.qml")
LD_index.loadNamedStyle(LD_index_style_path)
QgsProject.instance().addMapLayer(LD_index)

def add_mapIndex(LD_index, devArea_layer, layout):

    # Create Map Items in The Layout
    map2 = QgsLayoutItemMap(layout)
    map2.setRect(10,10,10,10)
    map2.setCrs(QgsCoordinateReferenceSystem('EPSG:32754'))

    layer_extent = devArea_layer.extent()
    layer_extent.grow(10000) # pass a sensible value depending on crs used and map scale
    map2.zoomToExtent(layer_extent)

    urlWithParams = 'type=xyz&url=https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
    EsriSat = QgsRasterLayer(urlWithParams, 'OpenStreetMap', 'wms')  

    if EsriSat.isValid():
        QgsProject.instance().addMapLayer(EsriSat)
    else:
        print('invalid layer')

    # Set an empty list of layers to deactivate all layers
    map2.setLayers([LD_index, devArea_layer,EsriSat])

    # # Calculate the new extent with double the size
    # new_extent = QgsRectangle(
    #     layer_extent.xMinimum(), #- layer_extent.width() / 1,
    #     layer_extent.yMinimum(), #- layer_extent.height() / 1,
    #     layer_extent.xMaximum(), #+ layer_extent.width() / 1,
    #     layer_extent.yMaximum() #+ layer_extent.height() / 1
    # )

    # # Set the new extent for the map item
    # map2.setExtent(new_extent)layoutsetTitle

    #map.setBackgroundColor(QColor(255,255,255, 0))layout
    map2.setFrameEnabled(True)
    map2.setFrameStrokeWidth(QgsLayoutMeasurement(0.1, QgsUnitTypes.LayoutMillimeters))
    map2.attemptMove(QgsLayoutPoint(223.5, 159.3, QgsUnitTypes.LayoutMillimeters))
    map2.attemptResize(QgsLayoutSize(68.8, 32.5, QgsUnitTypes.LayoutMillimeters)) # width, height
    # map2.storeCurrentLayerStyles()
    # map2.setKeepLayerSet(True)
    # map2.setKeepLayerStyles(True)

    # add_grid(map = map2, extent = gap_layer.extent(), text_size=3, FrameWidth=0.5, xyinterval=5000)

    return layout.addLayoutItem(map2)

add_mapIndex(LD_index, devArea_layer, layout)

exporter = QgsLayoutExporter(layout)
# exporter.exportToPdf(os.path.join(parent_dir + "/output/automation_map.pdf"), QgsLayoutExporter.PdfExportSettings())
output_pdf = r"D:/00. Geo-AI Apps/automation of gap and weed detection/lib/pyqgis/output/automation_map.pdf"

result = exporter.exportToPdf(
    output_pdf,
    QgsLayoutExporter.PdfExportSettings()
)

print("Export result:", result)

if result == QgsLayoutExporter.Success:
    print("PDF successfully exported!")
    print(output_pdf)
else:
    print("PDF export FAILED")

app.exitQgis()