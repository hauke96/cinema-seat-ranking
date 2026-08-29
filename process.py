#!/usr/bin/env python3

import click
import geojson
import geopy.distance
import json
import math
import sys

geojson.geometry.DEFAULT_PRECISION = 8

@click.group(chain=True)
def main():
    pass

@main.command()
@click.option('--seat-map', type=click.File('rb'))
@click.option('--rating-file', type=click.File('rb'))
def validate(seat_map, rating_file):
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

    pass

@main.command()
@click.option('--seat-map', type=click.Path(exists=True))
@click.option('--rating-file', type=click.Path(exists=True))
def update_estimates(seat_map, rating_file):
    foundError = False

    with open(seat_map, 'r+') as file:
        geojson_data = geojson.load(file)

        seatFeatures = [f for f in geojson_data['features'] if f['geometry']['type'] == 'Point' and f['properties']['row'] != None]
        knownSeats = [s for s in seatFeatures if s['properties'].get('rating') != None]
        unknownSeats = [s for s in seatFeatures if s['properties'].get('rating') == None]

        # Determine rating estimates according to the inverese distance weighting interpolation: https://en.wikipedia.org/wiki/Inverse_distance_weighting
        distancePowerParam = 10
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

            certaintyDistanceFactor = 0.05 # smaller value (i.e. closer to 0) means that the certainty spreads out and estimates for distant seats are considered relatively certain.
            certainty = max(0, -1 * certaintyDistanceFactor * math.pow(minDistanceToNextKnownSeat, 2) + 1) # +1 to get a max value of 1
            unknownSeat['properties']['certainty'] = certainty

            unknownSeat['properties']['rating_estimate'] = (sumOfWeightedRatings / sumOfWeights) * certainty

        for knownSeat in knownSeats:
            knownSeat['properties']['certainty'] = 1_000_000 # A non-infinity number but can be interpreted as "I'm a 100% sure"

        file.seek(0)
        file.write(json.dumps(geojson_data, indent=4))
        file.truncate()

if __name__ == '__main__':
    main()