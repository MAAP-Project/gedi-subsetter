#!/usr/bin/env bash

# Build the "production" image:
#
# - Assume pixi is already installed on the PATH
# - Build wheel for GEDI Subsetter
# - Install wheel for GEDI Subsetter
# - Install pixi production environment (i.e., all required dependencies)
# - Clean pixi cache and pixi default environment to reduce image size

set -euo pipefail

base_dir=$(dirname "$(dirname "$(readlink -f "$0")")")
manifest_path=(--manifest-path "${base_dir}/pyproject.toml")

# Build GEDI Subsetter wheel
pixi run "${manifest_path[@]}" build-wheel
# Install GEDI Subsetter
pixi run "${manifest_path[@]}" postinstall-production

# Verify installation
pixi run --no-progress --no-install --frozen --environment prod "${manifest_path[@]}" -- python -c '
import geopandas as gpd
import tempfile
import warnings
from shapely.geometry import Point

# Make sure pip install worked
from maap.maap import MAAP

# Make sure instantiation works
maap = MAAP()

warnings.filterwarnings("ignore", message=".*initial implementation of Parquet.*")

d = {"col1": ["name1", "name2"], "geometry": [Point(1, 2), Point(2, 1)]}
gdf = gpd.GeoDataFrame(d, crs="EPSG:4326")

with tempfile.TemporaryFile() as fp:
    gdf.to_parquet(fp)
    assert gdf.equals(gpd.read_parquet(fp))
'
