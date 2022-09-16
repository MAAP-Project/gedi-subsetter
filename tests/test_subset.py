import os
from typing import Any, Mapping

import geopandas as gpd
import pytest
from maap.maap import MAAP
from maap.Result import Granule
from returns.io import IOSuccess
from returns.maybe import Some

from gedi_subset.subset import SubsetGranuleProps, config_defaults, subset_granule


def test_subset_granule(
    maap: MAAP,
    h5_path: str,
    aoi_gdf: gpd.GeoDataFrame,
):
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
            ["agbd"],
            "l2_quality_flag == 1",
            output_dir,
        )
    )

    assert io_result == IOSuccess(Some(expected_path))


@pytest.mark.parametrize(
    "doi, columns, query, expected",
    [
        (
            "L4A",
            None,
            None,
            (
                "10.3334/ORNLDAAC/2056",
                ",".join(
                    [
                        "agbd",
                        "agbd_se",
                        "l2_quality_flag",
                        "l4_quality_flag",
                        "sensitivity",
                        "sensitivity_a2",
                    ]
                ),
                "".join(
                    [
                        "l2_quality_flag == 1",
                        " and l4_quality_flag == 1",
                        " and sensitivity > 0.95",
                        " and sensitivity_a2 > 0.95",
                    ]
                ),
            ),
        ),
        (
            "L2A",
            None,
            "l2_quality_flag == 1",
            (
                "10.5067/GEDI/GEDI02_A.002",
                ",".join(["rh", "sensitivity", "solar_elevation", "quality_flag"]),
                "l2_quality_flag == 1",
            ),
        ),
        (
            "L2A",
            "sensitivity,solar_elevation",
            None,
            (
                "10.5067/GEDI/GEDI02_A.002",
                "sensitivity,solar_elevation",
                "".join(
                    [
                        "rh > 100",
                        " and sensitivity > 0.9",
                        " and solar_elevation < 0",
                        " and quality_flag == 1",
                    ]
                ),
            ),
        ),
    ],
)
def test_config_defaults_success(
    config: Mapping[str, Any],
    doi: str,
    columns: str,
    query: str,
    expected: Mapping[str, Any],
):
    assert expected == config_defaults(config, doi, columns, query)


@pytest.mark.parametrize(
    "doi, columns, query",
    [
        ("10.5066/P9OGBGM6", None, None),
        ("L2B", None, "sensitivity > 0.9"),
        ("L2B", "RH100", None),
    ],
)
def test_config_defaults_failure(
    config: Mapping[str, Any], doi: str, columns: str, query: str
):

    with pytest.raises(ValueError):
        config_defaults(config, doi, columns, query)
