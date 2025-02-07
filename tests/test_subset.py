import os
from pathlib import Path
from typing import Iterator, cast

import geopandas as gpd
import pytest
import requests
from botocore.session import Session
from maap.maap import MAAP
from maap.Result import Granule
from moto.moto_server.threaded_moto_server import ThreadedMotoServer
from mypy_boto3_s3.client import S3Client
from returns.io import IOSuccess
from returns.maybe import Some
from typer import BadParameter

from gedi_subset.subset import SubsetGranuleProps, check_beams_option, subset_granule


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
    maap: MAAP,
    aoi_gdf: gpd.GeoDataFrame,
    tmp_path: Path,
):
    client = cast(S3Client, Session().create_client("s3", endpoint_url=moto_server_url))
    client.create_bucket(Bucket="mybucket")
    client.put_object(Bucket="mybucket", Key="temp.h5", Body=Path(h5_path).read_bytes())

    granule = Granule(
        {
            "Granule": {
                "GranuleUR": "foo",
                "OnlineAccessURLs": {
                    "OnlineAccessURL": {"URL": "s3://mybucket/temp.h5"}
                },
            }
        },
        awsAccessKey="",
        awsAccessSecret="",
        cmrFileUrl="",
        apiHeader={},
        dps=None,
    )

    # Since we have used a fixture to generate an h5 file, when subset_granule attempts
    # to download the granule, no download will occur since the file already exists,
    # which means we do not need to mock any S3 or HTTP calls.  Therefore, the result
    # we get should simply match the path of the h5 fixture file, except with a .gpq
    # extension, rather than an .h5 extension.

    expected_path = os.path.join(tmp_path, "temp.gpq")
    io_result = subset_granule(
        SubsetGranuleProps(
            fsspec_kwargs={
                "client_kwargs": {"endpoint_url": moto_server_url},
                "skip_instance_cache": True,
            },
            granule=granule,
            maap=maap,
            aoi_gdf=aoi_gdf,
            lat_col="lat_lowestmode",
            lon_col="lon_lowestmode",
            beams="all",
            columns=["agbd"],
            query="l2_quality_flag == 1",
            output_dir=tmp_path,
        )
    )

    assert io_result == IOSuccess(Some(expected_path))


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
