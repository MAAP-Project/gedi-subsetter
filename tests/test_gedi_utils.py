import os.path
import warnings
from typing import Set

import h5py
import pytest

from gedi_subset.gedi_utils import subset_hdf5

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import geopandas as gpd


def fixture_path(filename: str) -> str:
    return os.path.join(os.path.dirname(__file__), "fixtures", filename)


@pytest.mark.parametrize(
    "columns, query, n_expected_rows",
    [
        ({"agbd"}, "sensitivity < 0.9", 0),
        ({"agbd", "agbd_se"}, "sensitivity > 0.95 and l4_quality_flag == 1", 2),
        ({"sensitivity", "agbd"}, "agbd > 1 and l2_quality_flag == 1", 2),
        ({"sensitivity", "agbd", "agbd_se"}, "agbd_se > 3", 3),
        ({"agbd", "lat_lowestmode", "lon_lowestmode"}, "sensitivity >= 0.9", 4),
        ({"landsat_treecover"}, "landsat_treecover > 60.0", 4),
    ],
)
def test_subset_hdf5(
    h5_path: str,
    aoi_gdf: gpd.GeoDataFrame,
    columns: Set[str],
    query: str,
    n_expected_rows: int,
) -> None:
    with h5py.File(h5_path) as hdf5:
        gdf = subset_hdf5(hdf5, aoi_gdf, columns, query)

    expected_columns = columns | {"filename", "BEAM", "geometry"}

    assert set(gdf.columns) == expected_columns
    assert gdf.shape == (n_expected_rows, len(expected_columns))
