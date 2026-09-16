#!/usr/bin/env bash

source .venv/bin/activate

./process.py update-estimates --seat-map savoy.geojson

./process.py render

magick layout_ratings.pdf layout_ratings.png