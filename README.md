# Cinema seat ranking

Visualize the best seat in your cinema.

## Usage

### Setup

1. `python3 -m venv --system-site-packages .venv`
2. `source .venv/bin/activate`
3. `pip install click geojson geopy`

### Processing the data

1. `./process.py update-estimates --seat-map your-cinema-plan.geojson`
    * If no `--output ./path/to/file.geojson` is given, `./processed-data.geojson` will be used.

## Render as map

1. `./process.py render`
    * If no `--seat-map path/to/file.geojson` is given, `./processed-data.geojson` will be used.