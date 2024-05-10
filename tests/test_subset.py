import os
from pathlib import Path
from typing import cast

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
from s3fs import S3FileSystem
from typer import BadParameter

from gedi_subset.subset import SubsetGranuleProps, check_beams_option, subset_granule

# The following fixtures are simplifications of those found in the tests for s3fs at
# https://github.com/fsspec/s3fs/blob/main/s3fs/tests/test_s3fs.py.
# They are used to work around this issue: https://github.com/getmoto/moto/issues/6836

ip_address = "127.0.0.1"
port = 5555
endpoint_uri = f"http://{ip_address}:{port}/"


@pytest.fixture(scope="module")
def moto_server(aws_credentials):
    server = ThreadedMotoServer(ip_address=ip_address, port=port)
    server.start()
    yield
    server.stop()


@pytest.fixture(autouse=True)
def reset_s3_fixture():
    requests.post(f"{endpoint_uri}/moto-api/reset")


@pytest.fixture()
def fs(moto_server, h5_path: str):
    client = cast(S3Client, Session().create_client("s3", endpoint_url=endpoint_uri))
    client.create_bucket(Bucket="mybucket")
    client.put_object(Bucket="mybucket", Key="temp.h5", Body=Path(h5_path).read_bytes())

    S3FileSystem.clear_instance_cache()
    fs = S3FileSystem(client_kwargs={"endpoint_url": endpoint_uri})
    fs.invalidate_cache()

    yield fs


def test_subset_granule(
    fs: S3FileSystem, maap: MAAP, aoi_gdf: gpd.GeoDataFrame, tmp_path: Path
):
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
            fs,
            granule,
            maap,
            aoi_gdf,
            "lat_lowestmode",
            "lon_lowestmode",
            "all",
            ["agbd"],
            "l2_quality_flag == 1",
            tmp_path,
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
