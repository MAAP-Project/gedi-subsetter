#!/usr/bin/env bash

basedir=$(dirname "$(readlink -f "$0")")

set -xeuo pipefail

# Make sure conda is up to date
conda update -y -n base -c conda-forge conda

# Install dependencies from lock file for speed and reproducibility
case $(uname) in
Linux)
    platform="linux"
    ;;
Darwin)
    platform="osx"
    ;;
*)
    echo >&2 "Unsupported platform: $(uname)"
    exit 1
    ;;
esac

conda create -y -n gedi_subset --file "${basedir}/gedi-subset/conda-${platform}-64.lock"

# Install maap-py, since it cannot be specified in the lock file
conda run --no-capture-output -n gedi_subset pip install -r gedi-subset/requirements-maappy.txt

# Fail build if finicky mix of fiona and gdal isn't correct, so that we don't
# have to wait to execute a DPS job to find out.
conda run --no-capture-output -n gedi_subset python -c '
import geopandas as gpd
import tempfile
import warnings
from shapely.geometry import Point

# Make sure pip install worked
from maap.maap import MAAP

warnings.filterwarnings("ignore", message=".*initial implementation of Parquet.*")

d = {"col1": ["name1", "name2"], "geometry": [Point(1, 2), Point(2, 1)]}
gdf = gpd.GeoDataFrame(d, crs="EPSG:4326")

with tempfile.TemporaryFile() as fp:
    gdf.to_parquet(fp)
    assert gdf.equals(gpd.read_parquet(fp))
'
