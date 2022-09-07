import json
import pathlib
import re
from typing import Any, Mapping

import pytest
import requests
import responses
from maap.maap import MAAP
from maap.Result import Granule
from mypy_boto3_s3.client import S3Client
from returns.functions import raise_exception
from returns.unsafe import unsafe_perform_io

from gedi_subset.maapx import download_granule

EDC_CREDENTIALS_URL_PATTERN = re.compile(
    "https://.+/api/members/self/awsAccess/edcCredentials/.+"
)


def make_granule(metadata: Mapping[str, Any]) -> Granule:
    return Granule(
        metadata,
        awsAccessKey="",
        awsAccessSecret="",
        apiHeader={},
        cmrFileUrl="",
    )


def test_download_granule_no_s3credentials(
    maap: MAAP,
    s3: S3Client,
    tmp_path: pathlib.Path,
):
    s3.create_bucket(Bucket="mybucket")
    s3.put_object(Bucket="mybucket", Key="file.txt", Body="s3 contents")

    granule = make_granule(
        {
            "Granule": {
                "GranuleUR": "foo",
                "OnlineAccessURLs": {
                    "OnlineAccessURL": {"URL": "s3://mybucket/file.txt"}
                },
            }
        }
    )

    filename = unsafe_perform_io(
        download_granule(maap, str(tmp_path), granule).unwrap()
    )

    with open(filename) as f:
        assert f.read() == "s3 contents"


def test_download_granule_s3credentials_success(
    maap: MAAP,
    s3: S3Client,
    tmp_path: pathlib.Path,
):
    s3.create_bucket(Bucket="mybucket")
    s3.put_object(Bucket="mybucket", Key="file.txt", Body="s3 contents")

    creds = {
        "sessionToken": "mytoken",
        "accessKeyId": "mykeyid",
        "secretAccessKey": "myaccesskey",
    }
    granule = make_granule(
        {
            "Granule": {
                "GranuleUR": "foo",
                "OnlineAccessURLs": {
                    "OnlineAccessURL": {"URL": "s3://mybucket/file.txt"}
                },
                "OnlineResources": {
                    "OnlineResource": {"URL": "https://host/s3credentials"}
                },
            }
        }
    )

    with responses.RequestsMock() as mock:
        mock.get(url=EDC_CREDENTIALS_URL_PATTERN, status=200, body=json.dumps(creds))
        filename = unsafe_perform_io(
            download_granule(maap, str(tmp_path), granule).unwrap()
        )

    with open(filename) as f:
        assert f.read() == "s3 contents"


def test_download_granule_s3credentials_failure(
    maap: MAAP,
    s3: S3Client,
    tmp_path: pathlib.Path,
):
    s3.create_bucket(Bucket="mybucket")
    s3.put_object(Bucket="mybucket", Key="file.txt", Body="s3 contents")

    granule = make_granule(
        {
            "Granule": {
                "GranuleUR": "foo",
                "OnlineAccessURLs": {
                    "OnlineAccessURL": {"URL": "s3://mybucket/file.txt"}
                },
                "OnlineResources": {
                    "OnlineResource": {"URL": "https://host/s3credentials"}
                },
            }
        }
    )

    with pytest.raises(requests.exceptions.HTTPError, match="500"):
        with responses.RequestsMock() as mock:
            mock.get(url=EDC_CREDENTIALS_URL_PATTERN, status=500)
            download_granule(maap, str(tmp_path), granule).alt(raise_exception)


def test_download_granule_https_success(
    maap: MAAP,
    tmp_path: pathlib.Path,
):
    granule = make_granule(
        {
            "Granule": {
                "GranuleUR": "foo",
                "OnlineAccessURLs": {
                    "OnlineAccessURL": {"URL": "https://host/file.txt"}
                },
            }
        }
    )

    with responses.RequestsMock() as mock:
        mock.get(url="https://host/file.txt", status=200, body="https contents")
        filename = unsafe_perform_io(
            download_granule(maap, str(tmp_path), granule).unwrap()
        )

    with open(filename) as f:
        assert f.read() == "https contents"


def test_download_granule_https_failure(
    maap: MAAP,
    tmp_path: pathlib.Path,
):
    granule = make_granule(
        {
            "Granule": {
                "GranuleUR": "foo",
                "OnlineAccessURLs": {
                    "OnlineAccessURL": {"URL": "https://host/file.txt"}
                },
            }
        }
    )

    with pytest.raises(requests.exceptions.HTTPError, match="404"):
        with responses.RequestsMock() as mock:
            mock.get(url="https://host/file.txt", status=404)
            download_granule(maap, str(tmp_path), granule).alt(raise_exception)
