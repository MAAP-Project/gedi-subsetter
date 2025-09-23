from collections.abc import Callable
from pathlib import Path
from typing import Iterator, cast

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import requests
from botocore.session import Session
from moto.moto_server.threaded_moto_server import ThreadedMotoServer
from mypy_boto3_s3.client import S3Client
from typer import BadParameter

from gedi_subset.subset import (
    SubsetGranuleProps,
    check_beams_option,
    subset_granule,
    subset_granules,
)


# The following fixtures are simplifications of those found in the tests for s3fs at
# https://github.com/fsspec/s3fs/blob/main/s3fs/tests/test_s3fs.py.
@pytest.fixture(scope="module")
def moto_server_url(aws_credentials) -> Iterator[str]:
    server = ThreadedMotoServer(port=0)
    server.start()
    host, port = server.get_host_and_port()
    yield f"http://{host}:{port}"
    server.stop()


@pytest.fixture(autouse=True)
def reset_s3_fixture(moto_server_url: str):
    requests.post(f"{moto_server_url}/moto-api/reset")


def test_subset_granule(
    moto_server_url: str,
    h5_path: str,
    aoi_gdf: gpd.GeoDataFrame,
    tmp_path: Path,
):
    client = cast(S3Client, Session().create_client("s3", endpoint_url=moto_server_url))
    client.create_bucket(Bucket="mybucket")
    client.put_object(Bucket="mybucket", Key="temp.h5", Body=Path(h5_path).read_bytes())

    expected_path = tmp_path / "temp.parquet"

    subset_granule(
        SubsetGranuleProps(
            fsspec_kwargs={
                "client_kwargs": {"endpoint_url": moto_server_url},
                "skip_instance_cache": True,
            },
            granule_url="s3://mybucket/temp.h5",
            aoi_gdf=aoi_gdf,
            lat_col="lat_lowestmode",
            lon_col="lon_lowestmode",
            beams="all",
            columns=["agbd", "xvar"],
            query="l2_quality_flag == 1",
            output_dir=tmp_path,
        )
    )

    assert expected_path.exists()
    gdf = gpd.read_parquet(expected_path)
    assert isinstance(gdf.xvar[0], np.ndarray)


# @pytest.mark.parametrize("filename", ["subset.gpkg", "subset.parquet"])
@pytest.mark.parametrize(
    ["filename", "read_file", "two_d_row_type"],
    [
        ("subset.gpkg", gpd.read_file, str),
        ("subset.fgb", gpd.read_file, str),
        ("subset.parquet", gpd.read_parquet, np.ndarray),
    ],
)
def test_subset_granules(
    moto_server_url: str,
    h5_path: str,
    aoi_gdf: gpd.GeoDataFrame,
    tmp_path: Path,
    filename: str,
    read_file: Callable[[Path], pd.DataFrame],
    two_d_row_type: type,
):
    import logging

    client = cast(S3Client, Session().create_client("s3", endpoint_url=moto_server_url))
    client.create_bucket(Bucket="mybucket")
    client.put_object(
        Bucket="mybucket", Key="temp1.h5", Body=Path(h5_path).read_bytes()
    )
    client.put_object(
        Bucket="mybucket", Key="temp2.h5", Body=Path(h5_path).read_bytes()
    )

    dest = tmp_path / filename

    subset_granules(
        aoi_gdf=aoi_gdf,
        lat="lat_lowestmode",
        lon="lon_lowestmode",
        beams="all",
        columns=["agbd", "xvar"],
        query="l2_quality_flag == 1",
        output_dir=tmp_path,
        dest=dest,
        init_args=(logging.DEBUG,),
        granule_urls=(
            "s3://mybucket/temp1.h5",
            "s3://mybucket/temp2.h5",
        ),
        fsspec_kwargs={
            "client_kwargs": {"endpoint_url": moto_server_url},
            "skip_instance_cache": True,
        },
    )

    # Make sure the 2D xvar dataset roundtrips correctly retaining its data type.
    # Since we have selected xvar into a single column, we must ensure each
    # value is written and read back as a list (one per row in the xvar dataset).
    # We expect this to work only when the output (dest) format is parquet.
    # That is, only when dest is a '.parquet' file do we expect the row type to
    # retain its type as a numpy array.  In other cases, they get written as
    # strings, and thus read back in as strings, unfortunately.
    gdf = read_file(dest)
    assert isinstance(gdf.xvar[0], two_d_row_type)
    assert len(gdf.xvar) == 4


@pytest.mark.parametrize(
    "value",
    [
        "0100",
        "0111",
        "BEAM1001",
        "beam1010",
        "foo",
        "BEAMS0000",
        "all,power",
        "beam0000,beam0100",
        "BEAM0000,coverage",
    ],
)
def test_bad_check_beams_option(value: str):
    with pytest.raises(BadParameter):
        check_beams_option(value)


@pytest.mark.parametrize(
    "value, expected_value",
    [
        ("0000,0001,0010", "BEAM0000,BEAM0001,BEAM0010"),
        ("BEAM1011,BEAM1000,BEAM0110", "BEAM1011,BEAM1000,BEAM0110"),
        ("beam0000,beam0001,beam0010", "BEAM0000,BEAM0001,BEAM0010"),
        ("all", "ALL"),
        ("Coverage", "COVERAGE"),
        ("POWER", "POWER"),
        ("0000,Beam0001", "BEAM0000,BEAM0001"),
    ],
)
def test_valid_check_beams_option(value: str, expected_value: str):
    assert check_beams_option(value) == expected_value
