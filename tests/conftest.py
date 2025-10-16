import os

import boto3
import geopandas as gpd
import h5py
import pytest
import typing as t
from collections.abc import Iterable, Iterator
from maap.maap import MAAP
from moto import mock_aws
from mypy_boto3_s3.client import S3Client


@pytest.fixture(scope="module")
def aws_credentials() -> None:
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture(scope="function")
def s3(aws_credentials) -> Iterable[S3Client]:
    with mock_aws():
        yield boto3.client("s3", region_name="us-east-1")


@pytest.fixture(scope="session")
def maap() -> MAAP:
    return MAAP()


@pytest.fixture(scope="session")
def aoi_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame.from_features(
        [
            {
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [8.45, 2.35],
                            [14.35, 2.35],
                            [14.35, 0.0],
                            [8.45, 0.0],
                            [8.45, 2.35],
                        ]
                    ],
                },
            },
            {
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [8.45, 0.0],
                            [14.35, 0.0],
                            [14.35, -4.15],
                            [8.45, -4.15],
                            [8.45, 0.0],
                        ]
                    ],
                },
            },
        ],
    )


@pytest.fixture(scope="session")
def h5_path(tmp_path_factory: pytest.TempPathFactory) -> str:
    path = tmp_path_factory.mktemp("data") / "temp.h5"

    with h5py.File(path, "w") as h5_file:
        beam = h5_file.create_group("BEAM0000")
        beam.create_dataset("beam", data=[0, 0, 0], dtype="uint16")
        beam.create_dataset("shot_number", data=[0, 1, 2], dtype="uint64")
        beam.create_dataset("agbd", data=[1.271942, 1.3311168, 1.1160929], dtype="f4")
        beam.create_dataset("agbd_se", data=[3.057197, 3.053778, 3.06673], dtype="f4")
        beam.create_dataset("l2_quality_flag", data=[0, 1, 1], dtype="i1")
        beam.create_dataset("l4_quality_flag", data=[1, 0, 1], dtype="i1")
        beam.create_dataset("lat_lowestmode", data=[-1.82556, -9.82514, -1.82471])
        beam.create_dataset("lon_lowestmode", data=[12.06648, 12.06678, 12.06707])
        beam.create_dataset("lat_highestreturn", data=[-0.82556, -8.82514, -0.82471])
        beam.create_dataset("lon_highestreturn", data=[13.06648, 13.06678, 13.06707])
        beam.create_dataset("sensitivity", data=[0.9, 0.97, 0.99], dtype="f4")
        beam.create_dataset("xvar", data=[[10.0, 15.0], [20.0, 10.0], [15.0, 20.0]])
        land_cover = beam.create_group("land_cover_data")
        land_cover.create_dataset("landsat_treecover", data=[77.0, 98.0, 95.0])
        geolocation = beam.create_group("geolocation")
        geolocation.create_dataset(
            "latitude_instrument", data=[-2.82556, -10.82514, -2.82471]
        )
        geolocation.create_dataset(
            "longitude_instrument", data=[13.06648, 13.06678, 13.06707]
        )
        beam.attrs.create("description", "Coverage beam")

        beam = h5_file.create_group("BEAM1011")
        beam.create_dataset("beam", data=[11, 11, 11], dtype="uint16")
        beam.create_dataset("shot_number", data=[0, 1, 2], dtype="uint64")
        beam.create_dataset("agbd", data=[1.1715966, 1.630395, 3.5265787], dtype="f4")
        beam.create_dataset("agbd_se", data=[3.063243, 3.037882, 2.9968245], dtype="f4")
        beam.create_dataset("l2_quality_flag", data=[0, 1, 1], dtype="i1")
        beam.create_dataset("l4_quality_flag", data=[1, 0, 1], dtype="i1")
        beam.create_dataset("lat_lowestmode", data=[-1.82556, -9.82514, -1.82471])
        beam.create_dataset("lon_lowestmode", data=[12.06648, 12.06678, 12.06707])
        beam.create_dataset("lat_highestreturn", data=[-0.82556, -8.82514, -0.82471])
        beam.create_dataset("lon_highestreturn", data=[13.06648, 13.06678, 13.06707])
        beam.create_dataset("sensitivity", data=[0.93, 0.96, 0.98], dtype="f4")
        beam.create_dataset("xvar", data=[[15.0, 20.0], [25.0, 15.0], [20.0, 25.0]])
        land_cover = beam.create_group("land_cover_data")
        land_cover.create_dataset("landsat_treecover", data=[68.0, 85.0, 83.0])
        geolocation = beam.create_group("geolocation")
        geolocation.create_dataset(
            "latitude_instrument", data=[-2.82556, -10.82514, -2.82471]
        )
        geolocation.create_dataset(
            "longitude_instrument", data=[13.06648, 13.06678, 13.06707]
        )
        beam.attrs.create("description", "Full power beam")

    return str(path)


@pytest.fixture(scope="function")
def h5_file(h5_path: str) -> Iterator[h5py.File]:
    with h5py.File(h5_path) as h5:
        yield h5


@pytest.fixture(scope="function")
def beam0000(h5_file: h5py.File) -> h5py.Group:
    return t.cast(h5py.Group, h5_file["/BEAM0000"])
