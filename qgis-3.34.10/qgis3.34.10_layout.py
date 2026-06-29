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
    QgsLayerTree,
    QgsScaleBarSettings,
    QgsBasicNumericFormat
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
import math

CONFIG_VARIABLES = r"D:\00. Geo-AI Apps\automation of gap and weed detection\variables\qgis_layout_configuration.yaml"

# ── CONFIGURATION ──────────────────────────────────────────────────────────────
configuration_variable_path = CONFIG_VARIABLES
with open(configuration_variable_path, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

companies_select    = 'GPA'
logo_path           = cfg['logo']
map_comp_title      = cfg['comp_title']
north_arrow         = cfg['north_arrow']
gdb_path            = cfg['companies'][companies_select]['gdb_path']
gpkg_gaps_path      = cfg['companies'][companies_select]['gpkg_gaps_path']
mapIndex_xmin                = cfg['map_index_extent'][0]
mapIndex_ymin                = cfg['map_index_extent'][1]
mapIndex_xmax                = cfg['map_index_extent'][2]
mapIndex_ymax                = cfg['map_index_extent'][3]

today = str(date.today())
run_days = datetime.strptime(today, "%Y-%m-%d")

## Get the Parent Directory
script_dir  = os.path.dirname(os.path.abspath(__file__))
parent_dir = 'D:/00. Geo-AI Apps/automation of gap and weed detection/lib/pyqgis/'
print(parent_dir)


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
## 03.1 Gap Database
fiona_latest_gap = fiona.listlayers(gpkg_gaps_path)[-1]
# latest_gap = 'Gaps-Detection_GPA_20260611_AR'
gap_layer = QgsVectorLayer(
    f"{gpkg_gaps_path}|layername={fiona_latest_gap}",
    "Gap Detection",
    "ogr"
)
# print('latest_gap: ', fiona_latest_gap)
gap_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

## 03.2 Paddock
# gdb = ogr.Open(gdb_path)
# for i in range(gdb.GetLayerCount()):
#     layer = gdb.GetLayerByIndex(i)
#     print(layer.GetName())

paddock_layer = QgsVectorLayer(
    f"{gdb_path}|layername=paddock",
    "Paddock",
    "ogr"
)
paddock_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

## 03.3 Paddock
farm_layer = QgsVectorLayer(
    f"{gdb_path}|layername=Farm",
    "Farm",
    "ogr"
)
farm_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))



# print("Valid:", paddock.isValid())

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
    return legend_frame.setSymbol(frame_style(width = 0.3))
### 05.01 Main Map Frame for Side Information Map
addFrame(215.484, 4.515, 76.785, 200.969)
### 05.02 Navigation Info Frame
addFrame(215.484, 26.559, 76.785, 19.239)
### 05.03 Map Index
addFrame(215.484, 162.234, 76.785, 33.077)


# 06. MAIN MAP SETTING
## 06.01 Setup Frame & Call All Layers
def add_mainMap(gap_layer, paddock_layer, farm_layer):

    # Load the styles
    ## Gap
    gap_layer_style_path = (parent_dir +"/input/style/GapsArea_Style.qml")
    gap_layer.loadNamedStyle(gap_layer_style_path)
    QgsProject.instance().addMapLayer(gap_layer)
    ## Paddock
    paddock_layer_style_path = (parent_dir +"/input/style/Paddock_Style.qml")
    paddock_layer.loadNamedStyle(paddock_layer_style_path)
    QgsProject.instance().addMapLayer(paddock_layer)
    ## Farm
    farm_layer_style_path = (parent_dir +"/input/style/Farm_Style.qml")
    farm_layer.loadNamedStyle(farm_layer_style_path)
    QgsProject.instance().addMapLayer(farm_layer)

    
    map_item = QgsLayoutItemMap(layout)
    map_item.setLayers([farm_layer, gap_layer, paddock_layer])

    map_item.attemptMove(
        QgsLayoutPoint(
            4.434,
            4.515,
            QgsUnitTypes.LayoutMillimeters
        )
    )

    map_item.attemptResize(
        QgsLayoutSize(
            211.058,
            200.969,
            QgsUnitTypes.LayoutMillimeters
        )
    )

    # IMPORTANT
    extent = gap_layer.extent()
    extent.scale(1.1)      # 10% margin
    map_item.zoomToExtent(extent)

    # Round up scale
    current_scale = map_item.scale()
    rounded_scale = math.ceil(current_scale / 1000) * 1000
    map_item.setScale(rounded_scale)

    map_item.setFrameEnabled(True)
    map_item.setKeepLayerSet(True)
    map_item.setKeepLayerStyles(True)

    layout.addLayoutItem(map_item)

    map_item.refresh()

    return map_item

map_item = add_mainMap(gap_layer, paddock_layer, farm_layer)


# # 07. ADD LEGEND
# def addLegend(list_selected_layers):
#     # Add Legend Based on Checked Layers
#     legend = QgsLayoutItemLegend(layout)
#     # Set the title and font style
#     legend.setTitle("LEGEND")  # Set the title
#     font = QgsTextFormat()
#     font.setForcedBold(True)
#     font.setColor(Qt.GlobalColor.black)
#     font.setSize(8)
#     legend.rstyle(QgsLegendStyle.Title).setTextFormat(font)

#     legend.attemptMove(QgsLayoutPoint(217.850, 46.948, QgsUnitTypes.LayoutMillimeters))
#     legend.attemptResize(QgsLayoutSize(19.916, 3.392, QgsUnitTypes.LayoutMillimeters))
#     legend.setBackgroundEnabled(False)
#     legend.setAutoUpdateModel(False)  # This line is important!!

#     font = QgsTextFormat()
#     font.setForcedBold(True)
#     font.setColor(Qt.GlobalColor.black)
#     font.setSize(10)
#     legend.rstyle(QgsLegendStyle.Subgroup).setTextFormat(font)

#     # # SymbolLabel label style
#     font = QgsTextFormat()
#     font.setForcedBold(False)
#     font.setColor(Qt.GlobalColor.black)
#     font.setSize(10)
#     legend.rstyle(QgsLegendStyle.SymbolLabel).setTextFormat(font)

#     # Get the legend model and the root group
#     root_group  = project.layerTreeRoot()
#     legend_model = legend.model()
#     root_legend_group = legend_model.rootGroup()

#     # Remove all children from the root legend group
#     for child in root_legend_group.children():
#         root_legend_group.removeChildNode(child)


#     for child in root_group.children():
#         if isinstance(child, QgsLayerTreeLayer) and child.layer().name() in list_selected_layers:
#             root_legend_group.addChildNode(child.clone())

#     # Refresh the legend
#     legend.adjustBoxSize()
#     layout.addLayoutItem(legend)

# addLegend(list_selected_layers = ["Mekanisasi", "Blok Tanam"])


## Legend Titles
def legendTitles():
    # main legend
    titles = QgsLayoutItemLabel(layout)
    layout.addLayoutItem(titles)
    titles.setText("LEGEND")
    titles.setHAlign(Qt.AlignLeft)
    titles.setVAlign(Qt.AlignTop)
    titles.attemptResize(QgsLayoutSize(19.916, 3.392, QgsUnitTypes.LayoutMillimeters)) # width, height
    titles.attemptMove(QgsLayoutPoint(217.850, 46.948, QgsUnitTypes.LayoutMillimeters))
    titles_style = QgsTextFormat()
    titles_style.setColor(Qt.GlobalColor.black)
    titles_style.setSize(8)
    titles_style.setForcedBold(True)
    titles.setTextFormat(titles_style)
    
    # areaHA
    areaHA_title = QgsLayoutItemLabel(layout)
    layout.addLayoutItem(areaHA_title)
    areaHA_title.setText("Area (Ha)")
    areaHA_title.setHAlign(Qt.AlignRight)
    areaHA_title.setVAlign(Qt.AlignTop)
    areaHA_title.attemptResize(QgsLayoutSize(12.771, 4.070, QgsUnitTypes.LayoutMillimeters)) # width, height
    areaHA_title.attemptMove(QgsLayoutPoint(255.134, 49.284, QgsUnitTypes.LayoutMillimeters))
    areaHA_title_style = QgsTextFormat()
    areaHA_title_style.setColor(Qt.GlobalColor.black)
    areaHA_title_style.setSize(7)
    areaHA_title_style.setForcedBold(True)
    areaHA_title.setTextFormat(areaHA_title_style)
    
    # percentage
    percentage_title = QgsLayoutItemLabel(layout)
    layout.addLayoutItem(percentage_title)
    percentage_title.setText("Percentage (%)")
    percentage_title.setHAlign(Qt.AlignRight)
    percentage_title.setVAlign(Qt.AlignTop)
    percentage_title.attemptResize(QgsLayoutSize(21.547, 3.686, QgsUnitTypes.LayoutMillimeters)) # width, height
    percentage_title.attemptMove(QgsLayoutPoint(269.545, 49.284, QgsUnitTypes.LayoutMillimeters))
    percentage_title.setTextFormat(areaHA_title_style)
    
    gap_info_syle = QgsTextFormat()
    gap_info_syle.setColor(Qt.GlobalColor.black)
    gap_info_syle.setSize(7)
   
    # Gap
    gap_text = QgsLayoutItemLabel(layout)
    layout.addLayoutItem(gap_text)
    gap_text.setText("Gap")
    gap_text.setHAlign(Qt.AlignLeft)
    gap_text.setVAlign(Qt.AlignTop)
    gap_text.setTextFormat(gap_info_syle)
    gap_text.attemptMove(QgsLayoutPoint(224.481, 54.688, QgsUnitTypes.LayoutMillimeters))
    gap_text.attemptResize(QgsLayoutSize(7.403, 2.882, QgsUnitTypes.LayoutMillimeters)) # width, height

    # Growth Plant
    gap_text = QgsLayoutItemLabel(layout)
    layout.addLayoutItem(gap_text)
    gap_text.setText("Growth Plant")
    gap_text.setHAlign(Qt.AlignLeft)
    gap_text.setVAlign(Qt.AlignTop)
    gap_text.setTextFormat(gap_info_syle)
    gap_text.attemptMove(QgsLayoutPoint(223.997, 60.337, QgsUnitTypes.LayoutMillimeters))
    gap_text.attemptResize(QgsLayoutSize(18.903, 2.792, QgsUnitTypes.LayoutMillimeters)) # width, height

    # Next Target
    gap_text = QgsLayoutItemLabel(layout)
    layout.addLayoutItem(gap_text)
    gap_text.setText("Next Target")
    gap_text.setHAlign(Qt.AlignLeft)
    gap_text.setVAlign(Qt.AlignTop)
    gap_text.setTextFormat(gap_info_syle)
    gap_text.attemptMove(QgsLayoutPoint(223.997, 65.846, QgsUnitTypes.LayoutMillimeters))
    gap_text.attemptResize(QgsLayoutSize(14.807, 2.899, QgsUnitTypes.LayoutMillimeters)) # width, height
    

    return titles, areaHA_title, percentage_title, gap_text

legendTitles()

## Legend Items
def addLegendRectangle(
    layout,
    x,
    y,
    width=4,
    height=4,
    fill_color="#FF0000",
    outline=False,
):

    if outline == True:
        outline_color="#000000"
    elif outline == False:
        outline_color=fill_color
    
    rect = QgsLayoutItemShape(layout)
    rect.setShapeType(QgsLayoutItemShape.Rectangle)

    rect.attemptMove(
        QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters)
    )

    rect.attemptResize(
        QgsLayoutSize(width, height, QgsUnitTypes.LayoutMillimeters)
    )

    symbol = QgsFillSymbol.createSimple({
        "color": QColor(fill_color).name(),
        "outline_color": QColor(outline_color).name(),
        "outline_width": "0.2",
    })

    rect.setSymbol(symbol)
    layout.addLayoutItem(rect)

    return rect

## Gap Info
addLegendRectangle(layout, x=218.000, y=53.934, fill_color="#FF0000", outline=False)
addLegendRectangle(layout, x=218.000, y=59.809, fill_color="#33a02c", outline=False)
addLegendRectangle(layout, x=218.000, y=65.5, fill_color="#d8d8d8", outline=False)

# 08 - MAP TITLE
def mapTitle():
    main_title = QgsLayoutItemLabel(layout)
    layout.addLayoutItem(main_title)
    main_title.setText(f'{map_comp_title}')
    main_title.setHAlign(Qt.AlignCenter)
    main_title.setVAlign(Qt.AlignVCenter)
    main_title.attemptResize(QgsLayoutSize(54.480, 12.791, QgsUnitTypes.LayoutMillimeters)) # width, height
    main_title.attemptMove(QgsLayoutPoint(236.865, 7.147, QgsUnitTypes.LayoutMillimeters))
    main_title_style = QgsTextFormat()
    main_title_style.setColor(Qt.GlobalColor.black)
    main_title_style.setSize(10)
    main_title_style.setForcedBold(True)
    main_title.setTextFormat(main_title_style)
    return main_title

mapTitle()

# 09 - MAP TITLE
def mapDate():
    main_date = QgsLayoutItemLabel(layout)
    layout.addLayoutItem(main_date)
    main_date.setText("As of 31 December 2025")
    main_date.setHAlign(Qt.AlignCenter)
    main_date.setVAlign(Qt.AlignVCenter)
    main_date.attemptResize(QgsLayoutSize(40.784, 4.885, QgsUnitTypes.LayoutMillimeters)) # width, height
    main_date.attemptMove(QgsLayoutPoint(243.713, 18.609, QgsUnitTypes.LayoutMillimeters))
    main_date_style = QgsTextFormat()
    main_date_style.setColor(Qt.GlobalColor.black)
    main_date_style.setSize(8)
    main_date.setTextFormat(main_date_style)
    return main_date

mapDate()

# 10 - LOGO
def mapLogo(logo_path):
    main_logo = QgsLayoutItemPicture(layout)
    main_logo.setPicturePath(logo_path)
    # picture_item.setSize(100, 100) 
    main_logo.attemptResize(QgsLayoutSize(17.020, 17.889, QgsUnitTypes.LayoutMillimeters)) # width, height
    main_logo.attemptMove(QgsLayoutPoint(217.850, 7.425))
    layout.addLayoutItem(main_logo)

mapLogo(logo_path)

# help(QgsLayoutItemScaleBar)

# 09 - ADD SCALE BAR
def scaleBar():
    scalebar_item = QgsLayoutItemScaleBar(layout)
    scalebar_item.setLinkedMap(map_item)
    scalebar_item.setStyle('Single Box')
    scalebar_item.setUnits(QgsUnitTypes.DistanceMeters)
    scalebar_item.setNumberOfSegments(2)
    scalebar_item.setUnitsPerSegment(1000)
    scalebar_item.setHeight(0.7)
    scalebar_item.setLabelVerticalPlacement(QgsScaleBarSettings.LabelBelowSegment)

    # Create text format
    text_format = QgsTextFormat()
    font = QFont('MS Shell Dlg 2', 3)  #font setting
    text_format.setFont(font)
    text_format.setSize(3)              

    scalebar_item.setTextFormat(text_format)

    scalebar_item.setLabelBarSpace(0.5)
    scalebar_item.setUnitLabel('m')
    scalebar_item.attemptResize(QgsLayoutSize(33.902, 5.467, QgsUnitTypes.LayoutMillimeters)) # width, height
    scalebar_item.attemptMove(QgsLayoutPoint(227.567, 31.360))
    layout.addLayoutItem(scalebar_item)

    # print("Map scale:", map_item.scale())
    # print("Scale bar units:", scalebar_item.units())
    # print("Linked map:", scalebar_item.linkedMap())
    # print(scalebar_item.linkedMap())

    # print("Units per segment:", scalebar_item.unitsPerSegment())
    # print("Number of segments:", scalebar_item.numberOfSegments())
    # print("Segment size mode:", scalebar_item.segmentSizeMode())

scaleBar()

# 10 - ADD SCALE BAR
def mapCoordinateInfo():
    def coord_text_format():
        text_format = QgsTextFormat()
        font = QFont('MS Shell Dlg 2', 5)  #font setting
        text_format.setFont(font)
        text_format.setSize(5)
        return text_format
    
    # Coord Attributes
    coord_attributes = QgsLayoutItemLabel(layout)
    layout.addLayoutItem(coord_attributes)
    coord_attributes.setText("Grid System \nProjection \nDatum \nZone")
    coord_attributes.setHAlign(Qt.AlignLeft)
    coord_attributes.setVAlign(Qt.AlignTop)
    coord_attributes.attemptResize(QgsLayoutSize(15.838, 8.305, QgsUnitTypes.LayoutMillimeters)) # width, height
    coord_attributes.attemptMove(QgsLayoutPoint(228.946, 36.179, QgsUnitTypes.LayoutMillimeters))
    text_format = coord_text_format()
    coord_attributes.setTextFormat(text_format)
    # Coord Values
    coord_values = QgsLayoutItemLabel(layout)
    layout.addLayoutItem(coord_values)
    coord_values.setText(": Grid Geografis \n: UTM \n: WGS 84 \n: 54 S")
    coord_values.setHAlign(Qt.AlignLeft)
    coord_values.setVAlign(Qt.AlignTop)
    coord_values.attemptResize(QgsLayoutSize(15.838, 8.305, QgsUnitTypes.LayoutMillimeters)) # width, height
    coord_values.attemptMove(QgsLayoutPoint(245.050, 36.232, QgsUnitTypes.LayoutMillimeters))
   
    coord_values.setTextFormat(text_format)

    return coord_attributes, coord_values

mapCoordinateInfo()

# 11 - ADD SCALE NUMBER
def scaleNumeric():
    def coord_text_format():
        text_format = QgsTextFormat()
        font = QFont('MS Shell Dlg 2', 5)  #font setting
        text_format.setFont(font)
        text_format.setSize(5)
        return text_format
    
    # Scale text 
    scale_text = QgsLayoutItemLabel(layout)
    layout.addLayoutItem(scale_text)
    scale_text.setText("SCALE")
    scale_text.setHAlign(Qt.AlignLeft)
    scale_text.setVAlign(Qt.AlignTop)
    scale_text.attemptResize(QgsLayoutSize(5.394, 28.717, QgsUnitTypes.LayoutMillimeters)) # width, height
    scale_text.attemptMove(QgsLayoutPoint(228.946, 28.717, QgsUnitTypes.LayoutMillimeters))
    text_format = coord_text_format()
    scale_text.setTextFormat(text_format)

    
    numericscale_item = QgsLayoutItemScaleBar(layout)
    
    numericscale_item.setLinkedMap(map_item)
    numericscale_item.setStyle('Numeric')
    numericscale_item.attemptResize(QgsLayoutSize(14.989, 4.020, QgsUnitTypes.LayoutMillimeters)) # width, height
    numericscale_item.attemptMove(QgsLayoutPoint(235.405, 27.780, QgsUnitTypes.LayoutMillimeters))
    numericscale_item.setTextFormat(text_format)
    layout.addLayoutItem(numericscale_item)
    return scale_text

scaleNumeric()


def addLine(layout, x, y, length, orientation="horizontal", thickness=0.2, color=QColor(0, 0, 0)):

    line = QgsLayoutItemShape(layout)
    line.setShapeType(QgsLayoutItemShape.Rectangle)

    line.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))

    if orientation.lower() == "vertical":
        width = thickness
        height = length

    elif orientation.lower() == "horizontal":
        width = length
        height = thickness

    else:
        raise ValueError(
            "orientation must be 'vertical' or 'horizontal'"
        )

    line.attemptResize(
        QgsLayoutSize(
            width,
            height,
            QgsUnitTypes.LayoutMillimeters
        )
    )

    symbol = QgsFillSymbol.createSimple({
        "color": color.name(),
        "outline_style": "no"
    })

    line.setSymbol(symbol)

    layout.addLayoutItem(line)

    return line

### Title - North/Scale
addLine(layout=layout, x=262.993, y=26.559, length=19.3, orientation="vertical")

### Frame for Gap Precentage
addLine(layout=layout, x=218, y=58.888, length=74.269, orientation="horizontal")
addLine(layout=layout, x=218, y=64.545, length=74.269, orientation="horizontal")
addLine(layout=layout, x=218, y=70.2, length=51.168, orientation="horizontal")
addLine(layout=layout, x=247.245, y=54.079, length=16.3, orientation="vertical")
addLine(layout=layout, x=269.166, y=53.934, length=16.465, orientation="vertical")

# 10 - ADD NORTH ARROW
def northArrow():
    # Set Symbol
    picture_item = QgsLayoutItemPicture(layout)
    picture_item.setPicturePath(north_arrow) 
    picture_item.attemptResize(QgsLayoutSize(8.319, 11.864, QgsUnitTypes.LayoutMillimeters)) # width, height
    picture_item.attemptMove(QgsLayoutPoint(217.643, 33.537))
    layout.addLayoutItem(picture_item)

    # Scale N text
    north_text = QgsLayoutItemLabel(layout)
    layout.addLayoutItem(north_text)
    north_text.setText("N")
    north_text.setHAlign(Qt.AlignLeft)
    north_text.setVAlign(Qt.AlignTop)
    north_text.attemptResize(QgsLayoutSize(2.953, 4.102, QgsUnitTypes.LayoutMillimeters)) # width, height
    north_text.attemptMove(QgsLayoutPoint(220.528, 28.137, QgsUnitTypes.LayoutMillimeters))
    north_text_style = QgsTextFormat()
    north_text_style.setColor(Qt.GlobalColor.black)
    north_text_style.setSize(10)
    north_text_style.setForcedBold(True)
    north_text.setTextFormat(north_text_style)

    return picture_item, north_text

northArrow()

# 11 - MAP SOURCE INFO
def add_mapSource(layout, date):
    submber_data = QgsLayoutItemLabel(layout)
    submber_data.setHAlign(Qt.AlignLeft)
    submber_data.setVAlign(Qt.AlignTop)
    submber_data_style = QgsTextFormat()
    submber_data_style.setColor(Qt.GlobalColor.black)
    submber_data_style.setSize(5)
    submber_data.setText(f'SOURCE :\n' 
                         f'1. Tracking Team Land Preparation {date}\n' 
                         f'2. Foto Udara {date}')
    submber_data.setTextFormat(submber_data_style)

    #set size of label item. this step seems a little pointless to me but it doesn't work without it
    submber_data.adjustSizeToText() 
    submber_data.setMarginX(3)
    submber_data.attemptMove(QgsLayoutPoint(217.850, 197.276, QgsUnitTypes.LayoutMillimeters))
    submber_data.attemptResize(QgsLayoutSize(73.082, 6.823, QgsUnitTypes.LayoutMillimeters)) # width, height

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

    urlWithParams = 'type=xyz&url=https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
    EsriSat = QgsRasterLayer(urlWithParams, 'OpenStreetMap', 'wms')  

    if EsriSat.isValid():
        QgsProject.instance().addMapLayer(EsriSat)
    else:
        print('invalid layer')

    # Set an empty list of layers to deactivate all layers
    map2.setLayers([LD_index, devArea_layer,EsriSat])

    # Calculate the new extent with double the size
    new_extent = QgsRectangle(
        mapIndex_xmin, # xmin
        mapIndex_ymin, # ymin
        mapIndex_xmax, # xmax
        mapIndex_ymax # ymax
    )

    # Set the new extent for the map item
    map2.setExtent(new_extent)

    #map.setBackgroundColor(QColor(255,255,255, 0))layout
    map2.setFrameEnabled(True)
    map2.setFrameStrokeWidth(QgsLayoutMeasurement(0.1, QgsUnitTypes.LayoutMillimeters))
    map2.attemptMove(QgsLayoutPoint(230.549, 166.780, QgsUnitTypes.LayoutMillimeters))
    map2.attemptResize(QgsLayoutSize(44.840, 23.984, QgsUnitTypes.LayoutMillimeters)) # width, height
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