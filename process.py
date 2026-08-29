#!/usr/bin/env python3

import click
import geojson
import math

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
        # TODO exit 1

    pass

@main.command()
@click.option('--seat-map', type=click.File('wb'))
@click.option('--rating-file', type=click.File('rb'))
def update_estimates(seat_map, rating_file):
    foundError = False

    with seat_map as file:
        geojson_data = geojson.load(file)

    seatFeatures = [f for f in geojson_data['features'] if f['geometry']['type'] == 'Point' and f['properties']['row'] != None]
    knownSeats = [s for s in seatFeatures if s['properties']['rating'] != None]
    unknownSeats = [s for s in seatFeatures if s['properties']['rating'] == None]

    # Determine rating estimates according to the inverese distance weighting interpolation: https://en.wikipedia.org/wiki/Inverse_distance_weighting
    distancePowerParam = 2
    for unknownSeat in unknownSeats:
        sumOfWeights = 0.0
        sumOfWeightedRatings = 0.0

        for knownSeat in knownSeats:
            dx = unknownSeat['geometry']['coordinates'][0] - knownSeat['geometry']['coordinates'][0]
            dy = unknownSeat['geometry']['coordinates'][1] - knownSeat['geometry']['coordinates'][1]
            distance = math.sqrt(dx*dx + dy*dy)

            weight = 1.0 / math.pow(distance, distancePowerParam)

            sumOfWeights += weight
            sumOfWeightedRatings += weight * float(knownSeat['properties']['rating'])

        unknownSeat['properties']['rating_estimate'] = sumOfWeightedRatings / sumOfWeights

    print(geojson.dumps(unknownSeats))

if __name__ == '__main__':
    main()