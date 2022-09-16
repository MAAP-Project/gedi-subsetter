import os
import warnings
from typing import Any, Iterable, Mapping

import boto3
import h5py
import pytest
from maap.AWS import AWS
from maap.maap import MAAP
from moto import mock_s3
from mypy_boto3_s3.client import S3Client

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import geopandas as gpd


class MockMAAP(MAAP):
    """Mock MAAP class to avoid the need for a maap.cfg file for testing."""

    def __init__(self):
        self.aws = AWS(
            "",
            "",
            "https://host/api/members/self/awsAccess/edcCredentials/foo",
            dict(),
        )


@pytest.fixture(scope="function")
def aws_credentials() -> None:
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture(scope="function")
def s3(aws_credentials) -> Iterable[S3Client]:
    with mock_s3():
        yield boto3.client("s3", region_name="us-east-1")


@pytest.fixture(scope="function")
def maap() -> MAAP:
    return MockMAAP()


@pytest.fixture(scope="session")
def config() -> Mapping[str, Any]:
    return {
        "L4A": {
            "doi": "10.3334/ORNLDAAC/2056",
            "columns": [
                "agbd",
                "agbd_se",
                "l2_quality_flag",
                "l4_quality_flag",
                "sensitivity",
                "sensitivity_a2",
            ],
            "query": [
                "l2_quality_flag == 1",
                " and l4_quality_flag == 1",
                " and sensitivity > 0.95",
                " and sensitivity_a2 > 0.95",
            ],
        },
        "L2A": {
            "doi": "10.5067/GEDI/GEDI02_A.002",
            "columns": ["rh", "sensitivity", "solar_elevation", "quality_flag"],
            "query": [
                "rh > 100",
                " and sensitivity > 0.9",
                " and solar_elevation < 0",
                " and quality_flag == 1",
            ],
        },
    }


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
                            [14.35, -4.15],
                            [8.45, -4.15],
                            [8.45, 2.35],
                        ]
                    ],
                },
            }
        ],
    )


@pytest.fixture(scope="session")
def h5_path(tmp_path_factory: pytest.TempPathFactory) -> str:
    path = tmp_path_factory.mktemp("data") / "temp.h5"

    with h5py.File(path, "w") as h5_file:
        beam = h5_file.create_group("BEAM0000")
        beam.create_dataset("agbd", data=[1.271942, 1.3311168, 1.1160929], dtype="f4")
        beam.create_dataset("agbd_se", data=[3.057197, 3.053778, 3.06673], dtype="f4")
        beam.create_dataset("l2_quality_flag", data=[0, 1, 1], dtype="i1")
        beam.create_dataset("l4_quality_flag", data=[1, 0, 1], dtype="i1")
        beam.create_dataset("lat_lowestmode", data=[-1.82556, -9.82514, -1.82471])
        beam.create_dataset("lon_lowestmode", data=[12.06648, 12.06678, 12.06707])
        beam.create_dataset("sensitivity", data=[0.9, 0.97, 0.99], dtype="f4")
        land_cover = beam.create_group("land_cover_data")
        land_cover.create_dataset("landsat_treecover", data=[77.0, 98.0, 95.0])
        land_cover.create_dataset(
            "x_var", data=[[10.0, 15.0, 20.0], [10.0, 15.0, 20.0]]
        )

        beam = h5_file.create_group("BEAM0001")
        beam.create_dataset("agbd", data=[1.1715966, 1.630395, 3.5265787], dtype="f4")
        beam.create_dataset("agbd_se", data=[3.063243, 3.037882, 2.9968245], dtype="f4")
        beam.create_dataset("l2_quality_flag", data=[0, 1, 1], dtype="i1")
        beam.create_dataset("l4_quality_flag", data=[1, 0, 1], dtype="i1")
        beam.create_dataset("lat_lowestmode", data=[-1.82556, -9.82514, -1.82471])
        beam.create_dataset("lon_lowestmode", data=[12.06648, 12.06678, 12.06707])
        beam.create_dataset("sensitivity", data=[0.93, 0.96, 0.98], dtype="f4")
        land_cover = beam.create_group("land_cover_data")
        land_cover.create_dataset("landsat_treecover", data=[68.0, 85.0, 83.0])
        land_cover.create_dataset(
            "x_var", data=[[15.0, 20.0, 25.0], [15.0, 20.0, 25.0]]
        )

    return str(path)
