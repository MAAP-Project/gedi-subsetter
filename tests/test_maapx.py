import json
import pathlib
import re
from typing import Any, Mapping

import botocore.exceptions
import pytest
import requests
import responses
from maap.maap import MAAP
from maap.Result import Granule
from mypy_boto3_s3.client import S3Client

from gedi_subset.maapx import download_granule, find_collection

EDC_CREDENTIALS_URL_PATTERN = re.compile(
    "https://.+/api/members/self/awsAccess/edcCredentials/.+"
)


def make_granule(metadata: Mapping[str, Any]) -> Granule:
    return Granule(
        metadata,
        awsAccessKey="",
        awsAccessSecret="",
        cmrFileUrl="",
        apiHeader={},
        dps=None,
    )


def test_download_granule_no_s3credentials_success(
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

    # We expect to be able to download the file from S3 without needing to
    # obtain temporary credentials.  This test is to ensure that the function
    # does not fail when no S3 credentials are required.
    filename = download_granule(maap, str(tmp_path), granule, max_tries=1)

    with open(filename) as f:
        assert f.read() == "s3 contents"


def test_download_granule_aws_error(
    maap: MAAP,
    s3: S3Client,
    tmp_path: pathlib.Path,
):
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

    with pytest.raises(botocore.exceptions.ClientError, match="NoSuchBucket"):
        download_granule(maap, str(tmp_path), granule, max_tries=1)


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
                    "OnlineResource": {"URL": "https://success/s3credentials"}
                },
            }
        }
    )

    with responses.RequestsMock() as mock:
        mock.get(url=EDC_CREDENTIALS_URL_PATTERN, status=200, body=json.dumps(creds))
        filename = download_granule(maap, str(tmp_path), granule, max_tries=1)

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
                    "OnlineResource": {"URL": "https://failure/s3credentials"}
                },
            }
        }
    )

    with pytest.raises(requests.exceptions.HTTPError, match="500"):
        with responses.RequestsMock() as mock:
            mock.get(url=EDC_CREDENTIALS_URL_PATTERN, status=500)
            download_granule(maap, str(tmp_path), granule, max_tries=1)


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
        filename = download_granule(maap, str(tmp_path), granule, max_tries=1)

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
            download_granule(maap, str(tmp_path), granule, max_tries=1)


@pytest.mark.vcr
def test_find_collection_no_results(maap: MAAP):
    with pytest.raises(ValueError, match="No collection found"):
        find_collection(maap, {"doi": "no/such/doi"})


@pytest.mark.vcr
def test_find_collection_multiple_results(maap: MAAP):
    # This DOI is known to have multiple collections: one cloud-hosted and one not.
    with pytest.raises(ValueError, match="Multiple collections found"):
        find_collection(maap, {"doi": "10.5067/GEDI/GEDI01_B.002"})


@pytest.mark.vcr
def test_find_collection_cloud_hosted(maap: MAAP):
    gedi_l1b = find_collection(
        maap,
        {
            "doi": "10.5067/GEDI/GEDI01_B.002",
            "cloud_hosted": "true",
        },
    )
    assert "LPCLOUD" in gedi_l1b["concept-id"]
