# Cinema seat ranking

Visualize the best seat in your cinema.

## Usage

### Setup

1. `python3 -m venv --system-site-packages .venv`
2. `source .venv/bin/activate`
3. `pip install click geojson geopy`

### Processing the data

1. `./process.py update-estimates --seat-map your-cinema-plan.geojson --output processed-data.geojson`

## Render as map

1. `./process.py render`
    * The data is read from the file `processed-data.geojson`, which can be generated with the `update-estimates` command above.