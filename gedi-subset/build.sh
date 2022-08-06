#!/usr/bin/env bash

conda create -y -n gedi_subset --file "${basedir}/gedi-subset/environment/conda-${platform}-64.lock"

# Install maap-py, since it cannot be specified in the lock file
conda run --no-capture-output -n gedi_subset pip install -r "${basedir}/gedi-subset/environment/requirements-maappy.txt"

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