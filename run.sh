#!/usr/bin/env bash

source .venv/bin/activate

./process.py update-and-render --seat-map savoy.geojson

magick layout_ratings.pdf layout_ratings.png