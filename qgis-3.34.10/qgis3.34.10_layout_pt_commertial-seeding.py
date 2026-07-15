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
    QgsTextFormat,
    QgsLayoutItemLabel, 
    QgsLayoutItemPicture, 
    QgsLayoutItemScaleBar,
    QgsRectangle,
    QgsLayoutMeasurement,
    QgsLayerTreeLayer,
    QgsCategorizedSymbolRenderer,
    QgsLayoutItemLegend,
    QgsLegendStyle,
    QgsScaleBarSettings,
    )

from qgis.PyQt.QtCore import (
    Qt,
)

from qgis.PyQt.QtGui import (
    QColor,
    QFont,
)

import geopandas as gpd
import pandas
from datetime import date, datetime
import os
from osgeo import ogr
import fiona
import yaml
import math
import sys
from pathlib import Path

# Allow importing local helpers from the repository root
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from lib.summary_statistics import get_gap_summary_statistics

# ── CONFIGURATION ──────────────────────────────────────────────────────────────
configuration_variable_path = os.path.join(project_root, 'config.yaml')
with open(configuration_variable_path, 'r', encoding='utf-8') as f:
    cfg = yaml.safe_load(f)

companies_run       = cfg['companies_run']
logo_path           = cfg['logo']
north_arrow         = cfg['north_arrow']
qgis_apps           = cfg['qgis_apps']
qml_dir             = cfg['qml_dir']
dam_gpa_path        = cfg['dam_gpa_path']
c1                  = cfg['companies_alias']['c1']
c2                  = cfg['companies_alias']['c2']


today = date.today()
run_day = today.strftime("%d %B %Y")

def run_single_company(companies_select) -> None:

    map_title           = cfg['companies'][companies_select]['map_title']
    map_path            = cfg['companies'][companies_select]['map_path']
    gdb_path            = cfg['companies'][companies_select]['gdb_path']
    gpkg_gaps_path      = cfg['companies'][companies_select]['gpkg_gaps_path']
    mapIndex_xmin       = cfg['companies'][companies_select]['map_index_extent'][0]
    mapIndex_ymin       = cfg['companies'][companies_select]['map_index_extent'][1]
    mapIndex_xmax       = cfg['companies'][companies_select]['map_index_extent'][2]
    mapIndex_ymax       = cfg['companies'][companies_select]['map_index_extent'][3]
    
    # Ensure project is fresh for each run
    project = QgsProject.instance()
    project.clear()

    if companies_select == c1: # SEEDING AND COMMERTIAL CONFIGURATION
        seed_plant, seed_gap, commercial_plant, commercial_gap = get_gap_summary_statistics(gdb_path, gpkg_gaps_path)

        print("Gap summary statistics:", {
            "seed_plant_ha": round(seed_plant, 2),
            "seed_gap_ha": round(seed_gap, 2),
            "commercial_plant_ha": round(commercial_plant, 2),
            "commercial_gap_ha": round(commercial_gap, 2),
        })
    
        # Seeding
        seed_percentagePlant = seed_plant/(seed_gap + seed_plant)*100
        seedRound_percentagePlant = round(seed_percentagePlant,2)
        seed_percentageGap = seed_gap/(seed_gap + seed_plant)*100
        seedRound_percentageGap = round(seed_percentageGap,2)

    
    # CREATE QGIS PROJECT
    project = QgsProject.instance()
    project.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

    ## Gap Database
    fiona_latest_gap = fiona.listlayers(gpkg_gaps_path)[-1]
    gap_layer = QgsVectorLayer(
        f"{gpkg_gaps_path}|layername={fiona_latest_gap}",
        "Gap Detection",
        "ogr"
    )
    gap_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

    ## Paddock
    # gdb = ogr.Open(gdb_path)
    # for i in range(gdb.GetLayerCount()):
    #     layer = gdb.GetLayerByIndex(i)
    #     print(layer.GetName())


    # ADJUST LAYOUT BASED ON COMPANY
    if companies_select == c1:

        # MAIN MAP
        # Paddock Layer
        paddock_layer = QgsVectorLayer(
            f"{gdb_path}|layername=paddock",
            "Landuse Types",
            "ogr"
        )
        paddock_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
        # Paddock Toponomi Layer
        paddockToponimi_layer = QgsVectorLayer(
            f"{gdb_path}|layername=paddock",
            "Paddock Toponimi",
            "ogr"
        )
        paddockToponimi_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
        paddockToponimi_layer.setSubsetString("\"LANDUSETYP\" = 'CP'") # Filter only CP
        # Farm Layer
        farm_layer = QgsVectorLayer(
            f"{gdb_path}|layername=Farm",
            "Farm Boundary",
            "ogr"
        )
        farm_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

        # road Layer
        road_layer = QgsVectorLayer(
            f"{gdb_path}|layername=road",
            "Road",
            "ogr"
        )
        road_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

        # dam Layer
        dam_layer = QgsVectorLayer(
            dam_gpa_path,
            "Dam",
            "ogr"
        )
        dam_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

        # INDEX MAP
        # Paddock Index Layer
        paddockIndex_layer = QgsVectorLayer(
            f"{gdb_path}|layername=paddock",
            "Paddock",
            "ogr"
        )
        paddockIndex_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
        # Farm Index Layer
        farmIndex_layer = QgsVectorLayer(
            f"{gdb_path}|layername=Farm",
            "Farm",
            "ogr"
        )
        farmIndex_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
        # Paddock Geopandas Dataframe
        gdb_paddock = gpd.read_file(gdb_path, layer='paddock')
        paddock_cp = gdb_paddock[gdb_paddock['LANDUSETYP'] == 'CP']
        paddock_cp["Area_Ha"] = paddock_cp["Shape_Area"]/10000

    elif companies_select == c2 :

        # MAIN MAP
        # Paddock Layer
        paddock_layer = QgsVectorLayer(
            f"{gdb_path}|layername=Paddock",
            "Landuse Types",
            "ogr"
        )
        paddock_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
        # Paddock Toponomi Layer
        paddockToponimi_layer = QgsVectorLayer(
            f"{gdb_path}|layername=planting",
            "Paddock Toponimi",
            "ogr"
        )
        paddockToponimi_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
        # Farm Layer
        farm_layer = QgsVectorLayer(
            f"{gdb_path}|layername=Farm",
            "Farm Boundary",
            "ogr"
        )
        farm_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

        # road Layer
        road_layer = QgsVectorLayer(
            f"{gdb_path}|layername=road",
            "Road",
            "ogr"
        )
        road_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))

        # INDEX MAP
        # Paddock Index Layer
        paddockIndex_layer = QgsVectorLayer(
            f"{gdb_path}|layername=Paddock",
            "Paddock",
            "ogr"
        )
        paddockIndex_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
        # Farm Index Layer
        farmIndex_layer = QgsVectorLayer(
            f"{gdb_path}|layername=Farm",
            "Farm",
            "ogr"
        )
        farmIndex_layer.setCrs(QgsCoordinateReferenceSystem("EPSG:32754"))
        # Paddock Geopandas Dataframe
        paddock_cp = gpd.read_file(gdb_path, layer='planting')
        paddock_cp["Area_Ha"] = paddock_cp["Shape_Area"]/10000


    ## GET VALUES FOR MAIN MAP INFO
    gapAR_database = gpd.read_file(gpkg_gaps_path, layer=fiona_latest_gap)
    # Gap Ha
    gapHA = sum(gapAR_database[gapAR_database['cls'] == 'gaps spot']['cls_area_ha'])
    round_gapHA = round(gapHA, 2)
    # print(round_gapHA)
    # Growth Plant Ha
    plantHA = sum(gapAR_database[gapAR_database['cls'] == 'plant']['cls_area_ha'])
    round_plantHA = round(plantHA, 2)


    if companies_select == c1: # SEEDING AND COMMERTIAL CONFIGURATION
        # Commertial
        commercial_plant = plantHA - seed_plant
        commercial_gap = gapHA - seed_gap
        commertial_percentagePlant = commercial_plant/(commercial_gap + commercial_plant)*100
        commertialRound_percentagePlant = round(commertial_percentagePlant,2)
        seed_percentageGap = commercial_gap/(commercial_gap + commercial_plant)*100
        commertialRound_percentageGap = round(seed_percentageGap,2)

    # print(round_plantHA)
    # Percentage Gap
    percentageGAP = gapHA/(gapHA + plantHA)*100
    round_percentageGAP = round(percentageGAP,2)
    # print(round_percentageGAP)
    # Percentage Growth Plant
    percentagePlant = plantHA/(gapHA + plantHA)*100
    round_percentagePlant = round(percentagePlant,2)
    # print(round_percentagePlant)
    # print(round_percentagePlant+round_percentageGAP)
    # Photo latest and newest
    oldest_date = gapAR_database["photo_date"].min().strftime("%d %B %Y")
    newest_date = gapAR_database["photo_date"].max().strftime("%d %B %Y")
    # print(oldest_date)
    # print(newest_date)

    # Next Target
    nextTarget = round(sum(paddock_cp['Area_Ha']) - (gapHA + plantHA), 2)

    # PRODUCE LAYOUTING MANAGER
    manager = project.layoutManager()
    layout_name = "Automation Map"
    layout = manager.layoutByName(layout_name)
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(layout_name)
    manager.addLayout(layout)

    def frame_style(width):
        simple_fill = QgsSimpleFillSymbolLayer()
        fill_symbol = QgsFillSymbol()
        fill_symbol.changeSymbolLayer(0, simple_fill)
        simple_fill.setColor(Qt.GlobalColor.white)
        simple_fill.setStrokeColor(Qt.GlobalColor.black)
        simple_fill.setStrokeWidth(width)
        return fill_symbol

    # main_frame.setSymbol(frame_style(width = 0.1))

    ## MAP FRAME
    def addFrame(x,y,width,height):
        legend_frame = QgsLayoutItemShape(layout)
        legend_frame.setShapeType(QgsLayoutItemShape.Shape.Rectangle)
        legend_frame.setRect(0, 0, width,height)
        legend_frame.attemptMove(QgsLayoutPoint(x,y, QgsUnitTypes.LayoutMillimeters))
        layout.addLayoutItem(legend_frame)
        return legend_frame.setSymbol(frame_style(width = 0.3))
    ### Main Map Frame for Side Information Map
    addFrame(215.484, 4.515, 76.785, 200.969)
    ### Navigation Info Frame
    addFrame(215.484, 26.559, 76.785, 19.239)
    ### Map Index
    addFrame(215.484, 162.234, 76.785, 33.077)


    # MAIN MAP SETTING
    ## Setup Main Map Frame & Call All Layers
    def add_mainMap():

        # Load the styles
        ## Road
        road_layer_style_path = os.path.join(qml_dir, "roadStyle.qml")
        road_layer.loadNamedStyle(road_layer_style_path)
        QgsProject.instance().addMapLayer(road_layer)

        ## Road
        if companies_select == c1:
            dam_layer_style_path = os.path.join(qml_dir, "damStyle.qml")
            dam_layer.loadNamedStyle(dam_layer_style_path)
            QgsProject.instance().addMapLayer(dam_layer)

        ## Gap
        gap_layer_style_path = os.path.join(qml_dir, "gapsAreaStyle.qml")
        gap_layer.loadNamedStyle(gap_layer_style_path)
        QgsProject.instance().addMapLayer(gap_layer)
        ## Paddock
        paddock_layer_style_path = os.path.join(qml_dir, "paddockStyle.qml")
        paddock_layer.loadNamedStyle(paddock_layer_style_path)
        QgsProject.instance().addMapLayer(paddock_layer)
        ## Farm
        farmMain_layer = farm_layer
        farm_layer_style_path = os.path.join(qml_dir, "farmStyle.qml")
        farmMain_layer.loadNamedStyle(farm_layer_style_path)
        QgsProject.instance().addMapLayer(farmMain_layer)
        ## Paddock Toponimi
        if companies_select == c1:
            paddockToponimi_style_path = os.path.join(qml_dir, "paddockToponimiStyle.qml")
            paddockToponimi_layer.loadNamedStyle(paddockToponimi_style_path)
            QgsProject.instance().addMapLayer(paddockToponimi_layer)
            
            map_item = QgsLayoutItemMap(layout)
            map_item.setLayers([dam_layer, road_layer, paddockToponimi_layer, farmMain_layer, gap_layer, paddock_layer])
            
        elif companies_select == c2:
            paddockToponimi_style_path = os.path.join(qml_dir, "paddockToponimiStyle_2.qml")
            paddockToponimi_layer.loadNamedStyle(paddockToponimi_style_path)
            QgsProject.instance().addMapLayer(paddockToponimi_layer)

            map_item = QgsLayoutItemMap(layout)
            map_item.setLayers([road_layer, farmMain_layer, gap_layer, paddockToponimi_layer, paddock_layer])
        

        map_item.attemptMove(QgsLayoutPoint(4.434, 4.515, QgsUnitTypes.LayoutMillimeters))
        map_item.attemptResize(QgsLayoutSize(211.058, 200.969, QgsUnitTypes.LayoutMillimeters))

        # IMPORTANT
        extent = gap_layer.extent()
        extent.scale(1.1) # 10% margin
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

    map_item = add_mainMap()


    # ADD LEGEND
    def addLegend(list_selected_layers):
        # Add Legend Based on Checked Layers
        legend = QgsLayoutItemLegend(layout)
        # legend.setLegendFilterByMapEnabled(True) # Force to only visualize layer features within the extent
        # legend.setLinkedMap(map_item) # Force to only visualize layer features within the extent

        if companies_select == c1:
            legend.attemptMove(QgsLayoutPoint(215.963, 106, QgsUnitTypes.LayoutMillimeters))
            legend.attemptResize(QgsLayoutSize(31.936, 50.598, QgsUnitTypes.LayoutMillimeters))
        elif companies_select == c2:
            legend.attemptMove(QgsLayoutPoint(215.916, 72, QgsUnitTypes.LayoutMillimeters))
            legend.attemptResize(QgsLayoutSize(31.936, 50.598, QgsUnitTypes.LayoutMillimeters))

        legend.setBackgroundEnabled(False)
        legend.setAutoUpdateModel(False)  # This line is important!!

        font = QgsTextFormat()
        font.setForcedBold(True)
        font.setColor(Qt.GlobalColor.black)
        font.setSize(7)
        legend.rstyle(QgsLegendStyle.Subgroup).setTextFormat(font)

        # # SymbolLabel label style
        font = QgsTextFormat()
        font.setForcedBold(False)
        font.setColor(Qt.GlobalColor.black)
        font.setSize(7)
        legend.rstyle(QgsLegendStyle.SymbolLabel).setTextFormat(font)

        # Symbol size
        legend.setSymbolWidth(4)      # mm
        legend.setSymbolHeight(4)     # mm

        # Spacing between legend items
        legend.rstyle(QgsLegendStyle.Symbol).setMargin(QgsLegendStyle.Top, 1.5)
        legend.rstyle(QgsLegendStyle.Symbol).setMargin(QgsLegendStyle.Bottom, 1.5)
        
        # Get the legend model and the root group
        root_group  = project.layerTreeRoot()
        legend_model = legend.model() 
        root_legend_group = legend_model.rootGroup()

        # Remove all children from the root legend group
        for child in root_legend_group.children():
            root_legend_group.removeChildNode(child)

        for child in root_group.children():

            if isinstance(child, QgsLayerTreeLayer) and child.layer().name() in list_selected_layers:

                layer_clone = child.clone()

                # Only modify the Landuse Types legend
                if layer_clone.layer().name() == "Landuse Types":

                    renderer = layer_clone.layer().renderer()

                    categories = [
                        cat for cat in renderer.categories()
                        if cat.value() not in ("CP", "", None)
                    ]

                    layer_clone.layer().setRenderer(
                        QgsCategorizedSymbolRenderer(
                            renderer.classAttribute(),
                            categories
                        )
                    )

                root_legend_group.addChildNode(layer_clone)

        # Refresh the legend
        legend.adjustBoxSize()
        layout.addLayoutItem(legend)

    addLegend(list_selected_layers=["Farm Boundary","Landuse Types"])


    def addLegend2(list_selected_layers):
        # Add Legend Based on Checked Layers
        legend = QgsLayoutItemLegend(layout)
        # legend.setLegendFilterByMapEnabled(True) # Force to only visualize layer features within the extent
        # legend.setLinkedMap(map_item) # Force to only visualize layer features within the extent

        if companies_select == c1:
            legend.attemptMove(QgsLayoutPoint(251.330, 106, QgsUnitTypes.LayoutMillimeters))
            legend.attemptResize(QgsLayoutSize(29.627, 28.598, QgsUnitTypes.LayoutMillimeters))
        elif companies_select == c2:
            legend.attemptMove(QgsLayoutPoint(251.330, 72, QgsUnitTypes.LayoutMillimeters))
            legend.attemptResize(QgsLayoutSize(31.936, 50.598, QgsUnitTypes.LayoutMillimeters))

        legend.setBackgroundEnabled(False)
        legend.setAutoUpdateModel(False)  # This line is important!!

        font = QgsTextFormat()
        font.setForcedBold(True)
        font.setColor(Qt.GlobalColor.black)
        font.setSize(7)
        legend.rstyle(QgsLegendStyle.Subgroup).setTextFormat(font)

        # # SymbolLabel label style
        font = QgsTextFormat()
        font.setForcedBold(False)
        font.setColor(Qt.GlobalColor.black)
        font.setSize(7)
        legend.rstyle(QgsLegendStyle.SymbolLabel).setTextFormat(font)

        # Symbol size
        legend.setSymbolWidth(4)      # mm
        legend.setSymbolHeight(4)     # mm

        # Spacing between legend items
        legend.rstyle(QgsLegendStyle.Symbol).setMargin(QgsLegendStyle.Top, 1)
        legend.rstyle(QgsLegendStyle.Symbol).setMargin(QgsLegendStyle.Bottom, 1)
        
        # Get the legend model and the root group
        root_group  = project.layerTreeRoot()
        legend_model = legend.model() 
        root_legend_group = legend_model.rootGroup()

        # Remove all children from the root legend group
        for child in root_legend_group.children():
            root_legend_group.removeChildNode(child)

        for child in root_group.children():

            if isinstance(child, QgsLayerTreeLayer) and child.layer().name() in list_selected_layers:

                layer_clone = child.clone()

                # Only modify the Landuse Types legend
                if layer_clone.layer().name() == "Landuse Types":

                    renderer = layer_clone.layer().renderer()

                    categories = [
                        cat for cat in renderer.categories()
                        if cat.value() not in ("CP", "", None)
                    ]

                    layer_clone.layer().setRenderer(
                        QgsCategorizedSymbolRenderer(
                            renderer.classAttribute(),
                            categories
                        )
                    )

                root_legend_group.addChildNode(layer_clone)

        # Refresh the legend
        legend.adjustBoxSize()
        layout.addLayoutItem(legend)

    addLegend2(list_selected_layers=["Dam", "Road"])

    # # Add image to layout
    # image = QgsLayoutItemPicture(layout)
    # image.setPicturePath(r"G:\TEAM SHARE\Working Directory\Damar\github\qgis_automation-layout\qml\damSymbol.jpg")

    # # Set position and size
    # image.setRect(252.727, 111.940, 6.007, 3.284)  # x, y, width, height (mm)

    # # Or use this for more control:
    # # image.attemptMove(QgsLayoutPoint(252.727, 111.940, QgsUnitTypes.LayoutMillimeters))
    # # image.attemptResize(QgsLayoutSize(6.007, 3.284, QgsUnitTypes.LayoutMillimeters))

    # # Add to layout
    # layout.addLayoutItem(image)

    if companies_select == c1:
        picture_dam = QgsLayoutItemPicture(layout)
        picture_dam.setPicturePath(os.path.join(qml_dir, "damSymbol.jpg")) 
        picture_dam.attemptMove(QgsLayoutPoint(252.727, 113))
        picture_dam.attemptResize(QgsLayoutSize(6.007, 4, QgsUnitTypes.LayoutMillimeters)) # width, height
        layout.addLayoutItem(picture_dam)

    ## LEGEND TITLES
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
        areaHA_title.setText("Overall")
        areaHA_title.setHAlign(Qt.AlignLeft)
        areaHA_title.setVAlign(Qt.AlignTop)
        areaHA_title.attemptMove(QgsLayoutPoint(217.653, 52.120, QgsUnitTypes.LayoutMillimeters))
        areaHA_title.attemptResize(QgsLayoutSize(10.546, 2.699, QgsUnitTypes.LayoutMillimeters)) # width, height
        areaHA_title_style = QgsTextFormat()
        areaHA_title_style.setColor(Qt.GlobalColor.black)
        areaHA_title_style.setSize(6)
        areaHA_title_style.setForcedBold(True)
        areaHA_title.setTextFormat(areaHA_title_style)

        # areaHA
        areaHA_title = QgsLayoutItemLabel(layout)
        layout.addLayoutItem(areaHA_title)
        areaHA_title.setText("Area (Ha)")
        areaHA_title.setHAlign(Qt.AlignRight)
        areaHA_title.setVAlign(Qt.AlignTop)
        areaHA_title.attemptMove(QgsLayoutPoint(261.653, 52.120, QgsUnitTypes.LayoutMillimeters))
        areaHA_title.attemptResize(QgsLayoutSize(10.546, 4.070, QgsUnitTypes.LayoutMillimeters)) # width, height
        areaHA_title_style = QgsTextFormat()
        areaHA_title_style.setColor(Qt.GlobalColor.black)
        areaHA_title_style.setSize(6)
        areaHA_title_style.setForcedBold(True)
        areaHA_title.setTextFormat(areaHA_title_style)
        
        # percentage
        percentage_title = QgsLayoutItemLabel(layout)
        layout.addLayoutItem(percentage_title)
        percentage_title.setText("Percentage (%)")
        percentage_title.setHAlign(Qt.AlignRight)
        percentage_title.setVAlign(Qt.AlignTop)
        percentage_title.attemptMove(QgsLayoutPoint(273.567, 52.120, QgsUnitTypes.LayoutMillimeters))
        percentage_title.attemptResize(QgsLayoutSize(17.575, 3.686, QgsUnitTypes.LayoutMillimeters)) # width, height
        percentage_title.setTextFormat(areaHA_title_style)
        
        gap_info_syle = QgsTextFormat()
        gap_info_syle.setColor(Qt.GlobalColor.black)
        gap_info_syle.setSize(7)
    
        # Growth Plant
        gap_text = QgsLayoutItemLabel(layout)
        layout.addLayoutItem(gap_text)
        gap_text.setText("Growth Plant")
        gap_text.setHAlign(Qt.AlignLeft)
        gap_text.setVAlign(Qt.AlignTop)
        gap_text.setTextFormat(gap_info_syle)
        gap_text.attemptMove(QgsLayoutPoint(223.997, 57.392, QgsUnitTypes.LayoutMillimeters))
        gap_text.attemptResize(QgsLayoutSize(26.397, 2.882, QgsUnitTypes.LayoutMillimeters)) # width, height

        # Gap
        gap_text = QgsLayoutItemLabel(layout)
        layout.addLayoutItem(gap_text)
        gap_text.setText("Gap")
        gap_text.setHAlign(Qt.AlignLeft)
        gap_text.setVAlign(Qt.AlignTop)
        gap_text.setTextFormat(gap_info_syle)
        gap_text.attemptMove(QgsLayoutPoint(223.997, 63.173, QgsUnitTypes.LayoutMillimeters))
        gap_text.attemptResize(QgsLayoutSize(18.903, 2.792, QgsUnitTypes.LayoutMillimeters)) # width, height

        # Next Target
        gap_text = QgsLayoutItemLabel(layout)
        layout.addLayoutItem(gap_text)
        gap_text.setText("Under Age (Next Target)")
        gap_text.setHAlign(Qt.AlignLeft)
        gap_text.setVAlign(Qt.AlignTop)
        gap_text.setTextFormat(gap_info_syle)
        gap_text.attemptMove(QgsLayoutPoint(223.997, 68.682, QgsUnitTypes.LayoutMillimeters))
        gap_text.attemptResize(QgsLayoutSize(30.873, 2.899, QgsUnitTypes.LayoutMillimeters)) # width, height
        
        if companies_select == c1: # SEEDING AND COMMERTIAL CONFIGURATION
            # Seeding
            areaHA_title = QgsLayoutItemLabel(layout)
            layout.addLayoutItem(areaHA_title)
            areaHA_title.setText("Seeding")
            areaHA_title.setHAlign(Qt.AlignLeft)
            areaHA_title.setVAlign(Qt.AlignTop)
            areaHA_title.attemptMove(QgsLayoutPoint(222.008, 75.551, QgsUnitTypes.LayoutMillimeters))
            areaHA_title.attemptResize(QgsLayoutSize(10.546, 4.070, QgsUnitTypes.LayoutMillimeters)) # width, height
            areaHA_title_style = QgsTextFormat()
            areaHA_title_style.setColor(Qt.GlobalColor.black)
            areaHA_title_style.setSize(6)
            areaHA_title_style.setForcedBold(True)
            areaHA_title.setTextFormat(areaHA_title_style)

            # Commertial
            areaHA_title = QgsLayoutItemLabel(layout)
            layout.addLayoutItem(areaHA_title)
            areaHA_title.setText("Commertial")
            areaHA_title.setHAlign(Qt.AlignLeft)
            areaHA_title.setVAlign(Qt.AlignTop)
            areaHA_title.attemptMove(QgsLayoutPoint(222.008, 92.500, QgsUnitTypes.LayoutMillimeters))
            areaHA_title.attemptResize(QgsLayoutSize(13.397, 4.070, QgsUnitTypes.LayoutMillimeters)) # width, height
            areaHA_title_style = QgsTextFormat()
            areaHA_title_style.setColor(Qt.GlobalColor.black)
            areaHA_title_style.setSize(6)
            areaHA_title_style.setForcedBold(True)
            areaHA_title.setTextFormat(areaHA_title_style)
            
            # Seeding Growth Plant
            gap_text = QgsLayoutItemLabel(layout)
            layout.addLayoutItem(gap_text)
            gap_text.setText("Growth Plant")
            gap_text.setHAlign(Qt.AlignLeft)
            gap_text.setVAlign(Qt.AlignTop)
            gap_text.setTextFormat(gap_info_syle)
            gap_text.attemptMove(QgsLayoutPoint(228.997, 79.908, QgsUnitTypes.LayoutMillimeters))
            gap_text.attemptResize(QgsLayoutSize(26.397, 2.882, QgsUnitTypes.LayoutMillimeters)) # width, height

            # Seeding Gap
            gap_text = QgsLayoutItemLabel(layout)
            layout.addLayoutItem(gap_text)
            gap_text.setText("Gap")
            gap_text.setHAlign(Qt.AlignLeft)
            gap_text.setVAlign(Qt.AlignTop)
            gap_text.setTextFormat(gap_info_syle)
            gap_text.attemptMove(QgsLayoutPoint(228.997, 85.689, QgsUnitTypes.LayoutMillimeters))
            gap_text.attemptResize(QgsLayoutSize(18.903, 2.792, QgsUnitTypes.LayoutMillimeters)) # width, height

            # Commertial Growth Plant
            gap_text = QgsLayoutItemLabel(layout)
            layout.addLayoutItem(gap_text)
            gap_text.setText("Growth Plant")
            gap_text.setHAlign(Qt.AlignLeft)
            gap_text.setVAlign(Qt.AlignTop)
            gap_text.setTextFormat(gap_info_syle)
            gap_text.attemptMove(QgsLayoutPoint(228.997, 96.632, QgsUnitTypes.LayoutMillimeters))
            gap_text.attemptResize(QgsLayoutSize(26.397, 2.882, QgsUnitTypes.LayoutMillimeters)) # width, height

            # Commertial Gap
            gap_text = QgsLayoutItemLabel(layout)
            layout.addLayoutItem(gap_text)
            gap_text.setText("Gap")
            gap_text.setHAlign(Qt.AlignLeft)
            gap_text.setVAlign(Qt.AlignTop)
            gap_text.setTextFormat(gap_info_syle)
            gap_text.attemptMove(QgsLayoutPoint(228.997, 102.413, QgsUnitTypes.LayoutMillimeters))
            gap_text.attemptResize(QgsLayoutSize(18.903, 2.792, QgsUnitTypes.LayoutMillimeters)) # width, height

        
        return titles, areaHA_title, percentage_title, gap_text

    legendTitles()


    ## LEGEND MAIN INFO VALUES
    def legendMainInfoValues():
        
        keyStyle = QgsTextFormat()
        keyStyle.setColor(Qt.GlobalColor.black)
        keyStyle.setSize(7)
    
        # Growth Plant
        growthValue_text = QgsLayoutItemLabel(layout)
        layout.addLayoutItem(growthValue_text)
        growthValue_text.setText(str(round_plantHA))
        growthValue_text.setHAlign(Qt.AlignRight)
        growthValue_text.setVAlign(Qt.AlignTop)
        growthValue_text.setTextFormat(keyStyle)
        growthValue_text.attemptMove(QgsLayoutPoint(256.163, 57.376, QgsUnitTypes.LayoutMillimeters))
        growthValue_text.attemptResize(QgsLayoutSize(16.036, 2.913, QgsUnitTypes.LayoutMillimeters)) # width, height
        
        # Gap
        gapValue_text = QgsLayoutItemLabel(layout)
        layout.addLayoutItem(gapValue_text)
        gapValue_text.setText(str(round_gapHA))
        gapValue_text.setHAlign(Qt.AlignRight)
        gapValue_text.setVAlign(Qt.AlignTop)
        gapValue_text.setTextFormat(keyStyle)
        gapValue_text.attemptMove(QgsLayoutPoint(257.537, 63.059, QgsUnitTypes.LayoutMillimeters))
        gapValue_text.attemptResize(QgsLayoutSize(14.662, 3.074, QgsUnitTypes.LayoutMillimeters)) # width, height
    
        # Next Target
        nextTargetValue_text = QgsLayoutItemLabel(layout)
        layout.addLayoutItem(nextTargetValue_text)
        nextTargetValue_text.setText(str(nextTarget))
        nextTargetValue_text.setHAlign(Qt.AlignRight)
        nextTargetValue_text.setVAlign(Qt.AlignTop)
        nextTargetValue_text.setTextFormat(keyStyle)
        nextTargetValue_text.attemptMove(QgsLayoutPoint(262.257, 68.866, QgsUnitTypes.LayoutMillimeters))
        nextTargetValue_text.attemptResize(QgsLayoutSize(9.943, 2.605, QgsUnitTypes.LayoutMillimeters)) # width, height

        # Percentage Growth Plant
        growthPercentage_text = QgsLayoutItemLabel(layout)
        layout.addLayoutItem(growthPercentage_text)
        growthPercentage_text.setText(str(round_percentagePlant))
        growthPercentage_text.setHAlign(Qt.AlignRight)
        growthPercentage_text.setVAlign(Qt.AlignTop)
        growthPercentage_text.setTextFormat(keyStyle)
        growthPercentage_text.attemptMove(QgsLayoutPoint(275.834, 57.331, QgsUnitTypes.LayoutMillimeters))
        growthPercentage_text.attemptResize(QgsLayoutSize(15.308, 2.726, QgsUnitTypes.LayoutMillimeters)) # width, height

        # Percentage Gap
        gapPercentage_text = QgsLayoutItemLabel(layout)
        layout.addLayoutItem(gapPercentage_text)
        gapPercentage_text.setText(str(round_percentageGAP))
        gapPercentage_text.setHAlign(Qt.AlignRight)
        gapPercentage_text.setVAlign(Qt.AlignTop)
        gapPercentage_text.setTextFormat(keyStyle)
        gapPercentage_text.attemptMove(QgsLayoutPoint(282.045, 63.011, QgsUnitTypes.LayoutMillimeters))
        gapPercentage_text.attemptResize(QgsLayoutSize(9.097, 3.030, QgsUnitTypes.LayoutMillimeters)) # width, height
        
        
        if companies_select == c1:# SEEDING AND COMMERTIAL CONFIGURATION
            # Seeding Growth Plant
            growthValue_text = QgsLayoutItemLabel(layout)
            layout.addLayoutItem(growthValue_text)
            growthValue_text.setText(str(round(seed_plant, 2)))
            growthValue_text.setHAlign(Qt.AlignRight)
            growthValue_text.setVAlign(Qt.AlignTop)
            growthValue_text.setTextFormat(keyStyle)
            growthValue_text.attemptMove(QgsLayoutPoint(256.163, 79.892, QgsUnitTypes.LayoutMillimeters))
            growthValue_text.attemptResize(QgsLayoutSize(16.036, 2.913, QgsUnitTypes.LayoutMillimeters)) # width, height
            
            # Seeding Gap
            gapValue_text = QgsLayoutItemLabel(layout)
            layout.addLayoutItem(gapValue_text)
            gapValue_text.setText(str(round(seed_gap, 2)))
            gapValue_text.setHAlign(Qt.AlignRight)
            gapValue_text.setVAlign(Qt.AlignTop)
            gapValue_text.setTextFormat(keyStyle)
            gapValue_text.attemptMove(QgsLayoutPoint(257.537, 85.574, QgsUnitTypes.LayoutMillimeters))
            gapValue_text.attemptResize(QgsLayoutSize(14.662, 3.074, QgsUnitTypes.LayoutMillimeters)) # width, height

            # Seeding Percentage Growth Plant
            growthPercentage_text = QgsLayoutItemLabel(layout)
            layout.addLayoutItem(growthPercentage_text)
            growthPercentage_text.setText(str(seedRound_percentagePlant))
            growthPercentage_text.setHAlign(Qt.AlignRight)
            growthPercentage_text.setVAlign(Qt.AlignTop)
            growthPercentage_text.setTextFormat(keyStyle)
            growthPercentage_text.attemptMove(QgsLayoutPoint(275.834, 79.847, QgsUnitTypes.LayoutMillimeters))
            growthPercentage_text.attemptResize(QgsLayoutSize(15.308, 2.726, QgsUnitTypes.LayoutMillimeters)) # width, height

            # Seeding Percentage Gap
            gapPercentage_text = QgsLayoutItemLabel(layout)
            layout.addLayoutItem(gapPercentage_text)
            gapPercentage_text.setText(str(seedRound_percentageGap))
            gapPercentage_text.setHAlign(Qt.AlignRight)
            gapPercentage_text.setVAlign(Qt.AlignTop)
            gapPercentage_text.setTextFormat(keyStyle)
            gapPercentage_text.attemptMove(QgsLayoutPoint(282.045, 85.527, QgsUnitTypes.LayoutMillimeters))
            gapPercentage_text.attemptResize(QgsLayoutSize(9.097, 3.030, QgsUnitTypes.LayoutMillimeters)) # width, height

            # Commertial Growth Plant
            growthValue_text = QgsLayoutItemLabel(layout)
            layout.addLayoutItem(growthValue_text)
            growthValue_text.setText(str(round(commercial_plant, 3)))
            growthValue_text.setHAlign(Qt.AlignRight)
            growthValue_text.setVAlign(Qt.AlignTop)
            growthValue_text.setTextFormat(keyStyle)
            growthValue_text.attemptMove(QgsLayoutPoint(256.163, 96.616, QgsUnitTypes.LayoutMillimeters))
            growthValue_text.attemptResize(QgsLayoutSize(16.036, 2.913, QgsUnitTypes.LayoutMillimeters)) # width, height
            
            # Commertial Gap
            gapValue_text = QgsLayoutItemLabel(layout)
            layout.addLayoutItem(gapValue_text)
            gapValue_text.setText(str(round(commercial_gap, 2)))
            gapValue_text.setHAlign(Qt.AlignRight)
            gapValue_text.setVAlign(Qt.AlignTop)
            gapValue_text.setTextFormat(keyStyle)
            gapValue_text.attemptMove(QgsLayoutPoint(257.537, 102.272, QgsUnitTypes.LayoutMillimeters))
            gapValue_text.attemptResize(QgsLayoutSize(14.662, 3.074, QgsUnitTypes.LayoutMillimeters)) # width, height
            
            # Commertial Percentage Growth Plant
            growthPercentage_text = QgsLayoutItemLabel(layout)
            layout.addLayoutItem(growthPercentage_text)
            growthPercentage_text.setText(str(commertialRound_percentagePlant))
            growthPercentage_text.setHAlign(Qt.AlignRight)
            growthPercentage_text.setVAlign(Qt.AlignTop)
            growthPercentage_text.setTextFormat(keyStyle)
            growthPercentage_text.attemptMove(QgsLayoutPoint(275.834, 96.571, QgsUnitTypes.LayoutMillimeters))
            growthPercentage_text.attemptResize(QgsLayoutSize(15.308, 2.726, QgsUnitTypes.LayoutMillimeters)) # width, height

            # Commertial Percentage Gap
            gapPercentage_text = QgsLayoutItemLabel(layout)
            layout.addLayoutItem(gapPercentage_text)
            gapPercentage_text.setText(str(commertialRound_percentageGap))
            gapPercentage_text.setHAlign(Qt.AlignRight)
            gapPercentage_text.setVAlign(Qt.AlignTop)
            gapPercentage_text.setTextFormat(keyStyle)
            gapPercentage_text.attemptMove(QgsLayoutPoint(282.045, 102.251, QgsUnitTypes.LayoutMillimeters))
            gapPercentage_text.attemptResize(QgsLayoutSize(9.097, 3.030, QgsUnitTypes.LayoutMillimeters)) # width, height


        return growthValue_text, gapValue_text, gapPercentage_text, growthPercentage_text, nextTargetValue_text

    legendMainInfoValues()



    ## LEGEND SYMBOLS
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

    ## Add Legend Symbols
    addLegendRectangle(layout, x=218.000, y=56.771, fill_color="#33a02c", outline=False)
    addLegendRectangle(layout, x=218.000, y=62.603, fill_color="#FF0000", outline=False)
    addLegendRectangle(layout, x=218.000, y=68.245, fill_color="#d8d8d8", outline=False)

    if companies_select == c1: # SEEDING AND COMMERTIAL CONFIGURATION
        ## Seeding
        addLegendRectangle(layout, x=223.000, y=79.286, fill_color="#33a02c", outline=False)
        addLegendRectangle(layout, x=223.000, y=85.118, fill_color="#FF0000", outline=False)

        ## Commertial
        addLegendRectangle(layout, x=223.000, y=96.010, fill_color="#33a02c", outline=False)
        addLegendRectangle(layout, x=223.000, y=101.842, fill_color="#FF0000", outline=False)
        
    # MAP TITLE
    def mapTitle(companies_select):
        main_title = QgsLayoutItemLabel(layout)
        layout.addLayoutItem(main_title)
        if companies_select == c1:
            main_title.setText(map_title)
        elif companies_select == c2:
            main_title.setText(map_title)

        main_title.setHAlign(Qt.AlignCenter)
        main_title.setVAlign(Qt.AlignVCenter)
        main_title.attemptMove(QgsLayoutPoint(233.448, 7.964, QgsUnitTypes.LayoutMillimeters))
        main_title.attemptResize(QgsLayoutSize(58.971, 6.406, QgsUnitTypes.LayoutMillimeters)) # width, height
        main_title_style = QgsTextFormat()
        main_title_style.setColor(Qt.GlobalColor.black)
        main_title_style.setSize(9)
        main_title_style.setForcedBold(True)
        main_title.setTextFormat(main_title_style)

        sub_title = QgsLayoutItemLabel(layout)
        layout.addLayoutItem(sub_title)
        sub_title.setText('Gap Detection Map')
        sub_title.setHAlign(Qt.AlignCenter)
        sub_title.setVAlign(Qt.AlignVCenter)
        sub_title.attemptMove(QgsLayoutPoint(233.448, 13.544, QgsUnitTypes.LayoutMillimeters))
        sub_title.attemptResize(QgsLayoutSize(58.970, 4.885, QgsUnitTypes.LayoutMillimeters)) # width, height
        sub_title_style = QgsTextFormat()
        sub_title_style.setColor(Qt.GlobalColor.black)
        sub_title_style.setSize(8)
        sub_title_style.setForcedBold(True)
        sub_title.setTextFormat(sub_title_style)


        return main_title, sub_title

    mapTitle(companies_select)

    # MAP DATE
    def mapDate(run_day):
        main_date = QgsLayoutItemLabel(layout)
        layout.addLayoutItem(main_date)
        main_date.setText(f"As of {run_day}")
        main_date.setHAlign(Qt.AlignCenter)
        main_date.setVAlign(Qt.AlignVCenter)
        main_date.attemptMove(QgsLayoutPoint(233.448, 18.430, QgsUnitTypes.LayoutMillimeters))
        main_date.attemptResize(QgsLayoutSize(58.970, 4.885, QgsUnitTypes.LayoutMillimeters)) # width, height
        main_date_style = QgsTextFormat()
        main_date_style.setColor(Qt.GlobalColor.black)
        main_date_style.setSize(7)
        main_date.setTextFormat(main_date_style)
        return main_date

    mapDate(run_day)

    # MAP LOGO
    def mapLogo(logo_path):
        main_logo = QgsLayoutItemPicture(layout)
        main_logo.setPicturePath(logo_path)
        # picture_item.setSize(100, 100) 
        main_logo.attemptResize(QgsLayoutSize(17.020, 17.889, QgsUnitTypes.LayoutMillimeters)) # width, height
        main_logo.attemptMove(QgsLayoutPoint(217.850, 7.425))
        layout.addLayoutItem(main_logo)

    mapLogo(logo_path)
    # help(QgsLayoutItemScaleBar)

    # MAP SCALE BAR
    def scaleBar():
        scalebar_item = QgsLayoutItemScaleBar(layout)
        scalebar_item.setLinkedMap(map_item)
        scalebar_item.setStyle('Single Box')
        scalebar_item.setUnits(QgsUnitTypes.DistanceMeters)

        # scalebar_item.setUnitsPerSegment(1000)
        # Automatically fit width
        scalebar_item.setSegmentSizeMode(
            QgsScaleBarSettings.SegmentSizeFitWidth
        )

        scalebar_item.setNumberOfSegments(2)

        scalebar_item.setMinimumBarWidth(28)
        scalebar_item.setMaximumBarWidth(30)

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

    # MAP COORDINATE INFO
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

    # ADD SCALE NUMBER
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

    # ADD LINES
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
    addLine(layout=layout, x=218, y=61.725, length=74.269, orientation="horizontal") # 1st left horizontal
    addLine(layout=layout, x=218, y=67.381, length=74.269, orientation="horizontal") # 2nd left horizontal
    addLine(layout=layout, x=218, y=72.922, length=55.168, orientation="horizontal") # 3rd left horizontal
    addLine(layout=layout, x=255.243, y=56.916, length=16, orientation="vertical") # 1st left vertical
    addLine(layout=layout, x=273.166, y=56.771, length=16.3, orientation="vertical") # 2nd left vertical

    if companies_select == c1: # SEEDING AND COMMERTIAL CONFIGURATION
        ### Seeding Info
        addLine(layout=layout, x=222.158, y=84.241, length=70.111, orientation="horizontal") # 1st left horizontal
        addLine(layout=layout, x=222.158, y=89.897, length=70.111, orientation="horizontal") # 2nd left horizontal
        addLine(layout=layout, x=255.244, y=79.431, length=10.467, orientation="vertical") # 1st left vertical
        addLine(layout=layout, x=273.166, y=79.286, length=10.613, orientation="vertical") # 2nd left vertical

        ### Commertial Info
        addLine(layout=layout, x=222.158, y=100.964, length=70.111, orientation="horizontal") # 1st left horizontal
        addLine(layout=layout, x=222.158, y=106.621, length=70.111, orientation="horizontal") # 2nd left horizontal
        addLine(layout=layout, x=255.244, y=96.155, length=10.467, orientation="vertical") # 1st left vertical
        addLine(layout=layout, x=273.166, y=96.010, length=10.613, orientation="vertical") # 2nd left vertical

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
    def add_mapSource(layout, run_day, oldest_date, newest_date):
        mapSource = QgsLayoutItemLabel(layout)
        mapSource.setHAlign(Qt.AlignLeft)
        mapSource.setVAlign(Qt.AlignTop)
        mapSource_style = QgsTextFormat()
        mapSource_style.setColor(Qt.GlobalColor.black)
        mapSource_style.setSize(5)
        mapSource.setText(f'SOURCE :\n' 
                            f'1. Gap detection analysis {run_day}\n' 
                            f'2. Aerial photo from {oldest_date} to {newest_date}')
        mapSource.setTextFormat(mapSource_style)

        #set size of label item. this step seems a little pointless to me but it doesn't work without it
        mapSource.adjustSizeToText() 
        mapSource.setMarginX(3)
        mapSource.attemptMove(QgsLayoutPoint(217.850, 197.276, QgsUnitTypes.LayoutMillimeters))
        mapSource.attemptResize(QgsLayoutSize(73.082, 6.823, QgsUnitTypes.LayoutMillimeters)) # width, height

        layout.addLayoutItem(mapSource)

    add_mapSource(layout, run_day, oldest_date, newest_date)

    # 12 - MAP INDEX
    def add_mapIndex(farmIndex_layer, gap_layer, paddockIndex_layer, layout, companies_select):

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
        
        farmIndex_layer_style_path = os.path.join(qml_dir, "farmIndexStyle.qml")
        farmIndex_layer.loadNamedStyle(farmIndex_layer_style_path)
        QgsProject.instance().addMapLayer(farmIndex_layer)

        gap_layer_style_path = os.path.join(qml_dir, "gapsAreaStyle.qml")
        gap_layer.loadNamedStyle(gap_layer_style_path)
        QgsProject.instance().addMapLayer(gap_layer)

        paddockIndex_layer_style_path = os.path.join(qml_dir, "paddockIndexStyle.qml")
        paddockIndex_layer.loadNamedStyle(paddockIndex_layer_style_path)
        QgsProject.instance().addMapLayer(paddockIndex_layer)
            

        # Set an empty list of layers to deactivate all layers
        map2.setLayers([farmIndex_layer, gap_layer, paddockIndex_layer, EsriSat])

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

        return layout.addLayoutItem(map2)

    add_mapIndex(farmIndex_layer, gap_layer, paddockIndex_layer, layout, companies_select)

    exporter = QgsLayoutExporter(layout)
    
    if companies_select == c1:
        output_pdf = os.path.join(map_path + f"GPA_Gap Detection Map_{run_day}.pdf")
    elif companies_select == c2:
        output_pdf = os.path.join(map_path + f"MNM_Gap Detection Map_{run_day}.pdf")

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

    # app.exitQgis()


def main():
    QgsApplication.setPrefixPath(qgis_apps, True)
    app = QgsApplication([], False)
    app.initQgis()
    try:
        for companies_select in companies_run:
            print(f"Running for company: {companies_select}")
            run_single_company(companies_select)
    finally:
        app.exitQgis()

if __name__ == "__main__":
    main()

    