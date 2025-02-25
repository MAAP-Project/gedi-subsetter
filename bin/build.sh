#!/usr/bin/env bash

set -euo pipefail

# Install pixi if not already installed on the PATH

pixi=$(type -p pixi || true)

if [[ -z "${pixi}" ]]; then
    pixi_home=${HOME}/.pixi
    pixi=${pixi_home}/bin/pixi
    wget -qO- https://pixi.sh/install.sh | PIXI_HOME=${pixi_home} bash
fi

# Check that things appear to be installed correctly in the prod environment

base_dir=$(dirname "$(dirname "$(readlink -f "$0")")")

"${pixi}" run -q --no-progress -e prod --manifest-path "${base_dir}/pyproject.toml" -- python -c '
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
