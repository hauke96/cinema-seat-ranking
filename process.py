#!/usr/bin/env python3

import click
import geojson
import geopy.distance
import json
import math
import sys
from qgis.core import *

geojson.geometry.DEFAULT_PRECISION = 8

@click.group(chain=True)
def main():
    pass

@main.command()
@click.option('--seat-map', type=click.File('rb'))
def validate(seat_map):
    foundError = False

    with seat_map as file:
        geojson_data = geojson.load(file)

    seatFeatures = [f for f in geojson_data['features'] if f['geometry']['type'] == 'Point' and f['properties']['row'] != None]

    # Check seats
    rows = {f['properties']['row'] for f in seatFeatures}
    rows = sorted(rows)
    for row in rows:
        print(f"Row: {row}")
        seatsInRow = sorted([int(f['properties']['seat']) for f in seatFeatures if f['properties']['row'] == row])

        # Search for duplicate seats
        duplicateSeats = {s for s in seatsInRow if seatsInRow.count(s) > 1}
        if len(duplicateSeats) > 0:
            foundError = True
            print(f"  ERROR: Duplicate seats: {', '.join([str(x) for x in sorted(duplicateSeats)])}")

        # Search for missing seats
        expectedSeats = list(range(1, max(seatsInRow)+1))
        missingSeats = [s for s in expectedSeats if s not in seatsInRow]
        if len(missingSeats) > 0:
            foundError = True
            print(f"  ERROR: Missing seats: {', '.join([str(x) for x in sorted(missingSeats)])}")

    if foundError:
        print()
        print("ERRORS FOUND!")
        sys.exit(1)

@main.command()
@click.option('--seat-map', type=click.Path(exists=True))
@click.option('--output', type=click.Path())
def update_estimates(seat_map, output):
    foundError = False

    with open(seat_map, 'r') as file:
        print(f"Load data from {seat_map}")
        geojson_data = geojson.load(file)

        seatFeatures = [f for f in geojson_data['features'] if f['geometry']['type'] == 'Point' and f['properties']['row'] != None]
        knownSeats = [s for s in seatFeatures if s['properties'].get('rating') != None]
        unknownSeats = [s for s in seatFeatures if s['properties'].get('rating') == None]

        print(f"Found {len(seatFeatures)} seats")
        print(f"  {len(unknownSeats)} without rating")
        print(f"  {len(knownSeats)} with rating")

        distancePowerParam = 10 # Influence of distance between seats (lower = less influence)
        certaintyDistanceFactor = 0.025 # Influence of distance on certainty (smaller value = less influence, i.e. we're certain that distant estimates are correct)

        # Determine rating estimates according to the inverese distance weighting interpolation: https://en.wikipedia.org/wiki/Inverse_distance_weighting
        print("Process all seats")
        for unknownSeat in unknownSeats:
            sumOfWeights = 0.0
            sumOfWeightedRatings = 0.0
            minDistanceToNextKnownSeat = float("inf")

            for knownSeat in knownSeats:
                c1 = (unknownSeat['geometry']['coordinates'][0], unknownSeat['geometry']['coordinates'][1])
                c2 = (knownSeat['geometry']['coordinates'][0], knownSeat['geometry']['coordinates'][1])
                distance = geopy.distance.geodesic(c1, c2).m

                if distance < minDistanceToNextKnownSeat:
                    minDistanceToNextKnownSeat = distance

                weight = 1.0 / math.pow(distance, distancePowerParam)

                sumOfWeights += weight
                sumOfWeightedRatings += weight * float(knownSeat['properties']['rating'])

            certainty = max(0, -1 * certaintyDistanceFactor * math.pow(minDistanceToNextKnownSeat, 2) + 1) # +1 to get a max value of 1
            unknownSeat['properties']['certainty'] = certainty

            unknownSeat['properties']['rating_estimate'] = (sumOfWeightedRatings / sumOfWeights) * certainty

        print("Add certainty to known seats")
        for knownSeat in knownSeats:
            knownSeat['properties']['certainty'] = 1_000_000 # A non-infinity number but can be interpreted as "I'm a 100% sure"

    print(f"Write result to {output}")
    with open(output, 'w') as file:
        file.write(json.dumps(geojson_data, indent=4))

    print("Done")

@main.command()
def render():
    extent = None
    dataFile = "./processed-data.geojson"

    print(f"Read data file {dataFile}")
    with open(dataFile, 'r') as file:
        geojson_data = geojson.load(file)

        xCoords = []
        yCoords = []
        for feature in geojson_data['features']:
            props = feature['properties']
            if props.get('row') == None and props.get('seat') == None and props.get('cinema') == None and props.get('indoor') == None:
                continue

            geometry = feature['geometry']
            if geometry['type'] == 'Point':
                coord = geometry['coordinates']
                xCoords.append(coord[0])
                yCoords.append(coord[1])
            elif geometry['type'] == 'LineString':
                for coord in geometry['coordinates']:
                    xCoords.append(coord[0])
                    yCoords.append(coord[1])

        minX = min(xCoords)
        maxX = max(xCoords)

        minY = min(yCoords)
        maxY = max(yCoords)

        # Make the extent square for the layout
        # This require some math to make it wider or higher in the coordinate space.
        print("Ensure square extent")
        widthInM = geopy.distance.geodesic((minY, minX), (minY, maxX)).m
        heightInM = geopy.distance.geodesic((minY, minX), (maxY, minX)).m
        if widthInM > heightInM:
            differenceInM = widthInM - heightInM
            missingSpaceInM = differenceInM / 2
            yUnitPerMeter = (maxY - minY) / heightInM
            minY -= missingSpaceInM * yUnitPerMeter
            maxY += missingSpaceInM * yUnitPerMeter
        else:
            differenceInM = heightInM - widthInM
            missingSpaceInM = differenceInM / 2
            xUnitPerMeter = (maxX - minX) / widthInM
            minX -= missingSpaceInM * xUnitPerMeter
            maxX += missingSpaceInM * xUnitPerMeter

        # Add buffer
        print("Add buffer to extent")
        width = maxX - minX
        height = maxY - minY
        bufferFactor = 0.05 # Percentage what should be added to width and height
        minX -= width * bufferFactor
        maxX += width * bufferFactor
        minY -= height * bufferFactor
        maxY += height * bufferFactor

        extent = QgsRectangle(
            minX,
            minY,
            maxX,
            maxY
        )

        # Convert to CRS used in the map
        print("Convert extent to map CRS")
        sourceCrs = QgsCoordinateReferenceSystem(4326) # WGS84
        destCrs = QgsCoordinateReferenceSystem(3857) # Mercator
        transform = QgsCoordinateTransform(sourceCrs, destCrs, QgsProject.instance())
        extent = transform.transformBoundingBox(extent)

    print("Start application")
    qgs = QgsApplication([], False)
    qgs.initQgis()

    print("Load project")
    project = QgsProject.instance()
    project.read("./qgis-layout.qgs")
    layout_manager = project.layoutManager()
    layout = layout_manager.layoutByName("layout") # we assume this layout exists, so there is no "not None" check

    print("Search for map item")
    map_item = layout.itemById("Map")

    print("Load themes")
    themes = project.mapThemeCollection().mapThemes() # We assume there are themes, so we have no "not None" check below

    print("Prepare exporter")
    exporter = QgsLayoutExporter(layout)

    print("Export all themes")
    for theme_name in themes:
        print(f"Theme '{theme_name}'")

        # Set map item to follow the specific theme
        print(f"Theme '{theme_name}' - prepare map")
        map_item.setFollowVisibilityPreset(True)
        map_item.setFollowVisibilityPresetName(theme_name)
        map_item.setExtent(extent)

        # Force refresh/render
        print(f"Theme '{theme_name}' - render map")
        map_item.refresh()

        # Export
        print(f"Theme '{theme_name}' - prepare export")
        output_file = f"./layout_{theme_name.replace(" ", "-")}.pdf"
        export_settings = QgsLayoutExporter.PdfExportSettings()
        #export_settings.dpi = 300

        print(f"Theme '{theme_name}' - export")
        exporter.exportToPdf(output_file, export_settings)

    print("All themes exported successfully!")
    qgs.exitQgis()

if __name__ == '__main__':
    main()