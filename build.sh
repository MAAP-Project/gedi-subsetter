#!/usr/bin/env bash

set -xeuo pipefail

basedir=$(dirname "$(readlink -f "$0")")

# Make sure conda is updated to a version that supports the --no-capture-output option
conda install -y -n base -c conda-forge "conda>=4.13.0"

# Create conda env containing only conda-lock
conda create -y -n gedi_subset conda-lock

# Install dependencies from lock file for speed and reproducibility
conda run --no-capture-output -n gedi_subset conda lock install -n gedi_subset "${basedir}/environment/conda-lock.yml"

# Install maap-py, since it cannot be specified in the lock file
PIP_REQUIRE_VENV=0 conda env update -n gedi_subset --file "${basedir}/environment/environment-maappy.yml"

# Install development environment dependencies if the --dev flag is supplied
if [[ "${1:-}" == "--dev" ]]; then
   PIP_REQUIRE_VENV=0 conda env update -n gedi_subset --file "${basedir}/environment/environment-dev.yml"
fi

conda run --no-capture-output -n gedi_subset PIP_REQUIRE_VENV=0 python -m pip install -e "${basedir}"

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
