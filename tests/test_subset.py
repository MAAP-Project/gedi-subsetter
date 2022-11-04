import os
from pathlib import Path

import geopandas as gpd
import pytest
from maap.maap import MAAP
from maap.Result import Granule
from returns.io import IOSuccess
from returns.maybe import Some
from typer import BadParameter

from gedi_subset.subset import SubsetGranuleProps, check_beams_option, subset_granule


def test_subset_granule(maap: MAAP, h5_path: str, aoi_gdf: gpd.GeoDataFrame):
    output_dir = os.path.dirname(h5_path)
    filename = os.path.basename(h5_path)
    granule = Granule(
        {
            "Granule": {
                "GranuleUR": "foo",
                "OnlineAccessURLs": {
                    "OnlineAccessURL": {"URL": f"s3://mybucket/{filename}"}
                },
            }
        },
        awsAccessKey="",
        awsAccessSecret="",
        apiHeader={},
        cmrFileUrl="",
    )

    # Since we have used a fixture to generate an h5 file, when subset_granule attempts
    # to download the granule, no download will occur since the file already exists,
    # which means we do not need to mock any S3 or HTTP calls.  Therefore, the result
    # we get should simply match the path of the h5 fixture file, except with a .gpq
    # extension, rather than an .h5 extension.

    root, _ = os.path.splitext(h5_path)
    expected_path = f"{root}.gpq"
    io_result = subset_granule(
        SubsetGranuleProps(
            granule,
            maap,
            aoi_gdf,
            "lat_lowestmode",
            "lon_lowestmode",
            "all",
            ["agbd"],
            "l2_quality_flag == 1",
            Path(output_dir),
        )
    )

    assert io_result == IOSuccess(Some(expected_path))


def test_bad_check_beams_option(value="0100"):
    with pytest.raises(BadParameter):
        check_beams_option(value)
