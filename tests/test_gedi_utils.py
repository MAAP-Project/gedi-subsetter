import os.path
import warnings
from typing import Optional, Set

import h5py
import pytest

from gedi_subset.gedi_utils import subset_hdf5

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import geopandas as gpd


def fixture_path(filename: str) -> str:
    return os.path.join(os.path.dirname(__file__), "fixtures", filename)


@pytest.mark.parametrize(
    "lat, lon, columns, query, n_expected_rows",
    [
        # Test: Varying columns and queries
        ("lat_lowestmode", "lon_lowestmode", {"agbd"}, "sensitivity < 0.9", 0),
        (
            "lat_lowestmode",
            "lon_lowestmode",
            {"agbd", "agbd_se"},
            "sensitivity > 0.95 and l4_quality_flag == 1",
            2,
        ),
        (
            "lat_lowestmode",
            "lon_lowestmode",
            {"sensitivity", "agbd"},
            "agbd > 1 and l2_quality_flag == 1",
            2,
        ),
        (
            "lat_lowestmode",
            "lon_lowestmode",
            {"sensitivity", "agbd", "agbd_se"},
            "agbd_se > 3",
            3,
        ),
        (
            "lat_lowestmode",
            "lon_lowestmode",
            {"agbd", "lat_lowestmode", "lon_lowestmode"},
            "sensitivity >= 0.9",
            4,
        ),
        # Test: (n)D datasets
        (
            "lat_lowestmode",
            "lon_lowestmode",
            {"x_var0"},
            "l2_quality_flag == 1 & sensitivity > 0.9",
            2,
        ),
        # Test: nested group datasets
        (
            "lat_lowestmode",
            "lon_lowestmode",
            {"land_cover_data/landsat_treecover"},
            "land_cover_data.landsat_treecover > 60.0",
            4,
        ),
        (
            "lat_lowestmode",
            "lon_lowestmode",
            {"land_cover_data/landsat_treecover"},
            "`land_cover_data/landsat_treecover` > 60.0",
            4,
        ),
        (
            "lat_lowestmode",
            "lon_lowestmode",
            {"sensitivity", "agbd", "agbd_se"},
            "sensitivity > 0.96",
            2,
        ),
        # Test: Empty query algorithm input
        (
            "lat_lowestmode",
            "lon_lowestmode",
            {"sensitivity", "agbd", "agbd_se"},
            None,
            4,
        ),
        ("lat_lowestmode", "lon_lowestmode", {"sensitivity"}, None, 4),
        # Test: Varying lat/lon
        (
            "lat_highestreturn",
            "lon_highestreturn",
            {"sensitivity"},
            "sensitivity > 0.95 and l4_quality_flag == 1",
            2,
        ),
        (
            "geolocation/latitude_instrument",
            "geolocation/longitude_instrument",
            {"sensitivity"},
            "sensitivity > 0.95 and l4_quality_flag == 1",
            2,
        ),
    ],
)
def test_subset_hdf5(
    h5_path: str,
    aoi_gdf: gpd.GeoDataFrame,
    lat: str,
    lon: str,
    columns: Set[str],
    query: Optional[str],
    n_expected_rows: int,
) -> None:
    with h5py.File(h5_path) as hdf5:
        gdf = subset_hdf5(hdf5, aoi_gdf, lat, lon, list(columns), query)

    expected_columns = columns | {"filename", "BEAM", "geometry"}

    assert set(gdf.columns) == expected_columns
    assert gdf.shape == (n_expected_rows, len(expected_columns))

    # Make sure there are no NaN values.  If there is a NaN somewhere, that means that
    # we either have a bug, or we didn't construct our fixture data correctly, so we
    # should first verify the correctness of our fixture data, otherwise we might spend
    # unnecessary time hunting down a non-existent bug.
    assert gdf.notna().all(axis=None)
