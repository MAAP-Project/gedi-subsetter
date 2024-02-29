"""Functions providing convenience and safety for maap-py classes and methods.

Collection functions:

- `find_collection` attempts to find a single collection

Granule functions:

- `download_granule` attempts to download a granule file
"""

import logging
import operator
import random
from typing import Callable, Mapping, Never, Optional, ParamSpec, TypedDict, TypeVar

import backoff
import boto3
import botocore.exceptions
import botocore.session
import requests
from cachetools import FIFOCache, TTLCache, cached
from maap.maap import MAAP
from maap.Result import Collection, Granule
from returns.io import IOResultE, impure_safe
from returns.pipeline import flow, pipe
from returns.pointfree import bind_result, lash
from returns.result import Failure, safe

from gedi_subset import fp

logger = logging.getLogger(__name__)


__all__ = [
    "AWSCredentials",
    "download_granule",
    "find_collection",
]

T = TypeVar("T")
P = ParamSpec("P")


class AWSCredentials(TypedDict):
    accessKeyId: str
    secretAccessKey: str
    sessionToken: str


def _is_s3_credentials_online_resource(resource: Mapping[str, str]) -> bool:
    """Determine whether or not a granule's online resource is an S3 credentials
    endpoint.
    """
    url = resource.get("URL", "").lower()
    description = resource.get("Description", "").lower()

    # TODO: is this sufficient for identifying URL for obtaining S3 credentials?
    return url and url.endswith("/s3credentials") or "credentials" in description


def _s3_credentials_endpoint(granule: Granule) -> Optional[str]:
    """Return the S3 credentials endpoint for a granule.

    Parameters
    ----------
    granule
        The granule for which to obtain the S3 credentials endpoint.

    Returns
    -------
    url
        The S3 credentials endpoint URL or `None` if no S3 credentials endpoint
        is found.
    """
    granule = granule.get("Granule", {})
    resources = granule.get("OnlineResources", {}).get("OnlineResource", [])
    # OnlineResources.OnlineResource is a list only if there are multiple
    # resources, so when there is only one resource, we must put it in a list.
    # This is due to how the XML is parsed by the `xmltodict` library.
    resources = resources if isinstance(resources, list) else [resources]

    # We assume there is only one S3 credentials endpoint for a granule.
    if s3_resource := next(filter(_is_s3_credentials_online_resource, resources), None):
        return s3_resource["URL"]

    return None


@cached(cache=TTLCache(maxsize=1, ttl=55 * 60), key=lambda _, endpoint: endpoint)
def _s3_credentials(maap: MAAP, endpoint: str) -> AWSCredentials | Never:
    """Obtain short-term AWS credentials from an S3 credentials endpoint."""

    logger.debug(f"Obtaining S3 credentials from {endpoint}")

    return maap.aws.earthdata_s3_credentials(endpoint)


@cached(cache=FIFOCache(maxsize=1), key=lambda creds: creds["sessionToken"])
def _setup_default_boto3_session(creds: AWSCredentials) -> None:
    """Set up the default boto3 session using the specified credentials."""

    logger.debug("Setting up default boto3 session with new credentials")

    boto3.setup_default_session(
        aws_access_key_id=creds["accessKeyId"],
        aws_secret_access_key=creds["secretAccessKey"],
        aws_session_token=creds["sessionToken"],
        region_name="us-west-2",
        botocore_session=botocore.session.Session(),
    )


def _fatal_request_error(e: Exception) -> bool:
    _RETRYABLE_STATUS_CODES = {
        408,  # Request Timeout
        429,  # Too Many Requests
        500,  # Internal Server Error
        502,  # Bad Gateway
        503,  # Service Unavailable
        504,  # Gateway Timeout
    }

    if isinstance(e, requests.exceptions.RequestException):
        status_code = e.response.status_code if e.response is not None else 0
        return status_code not in _RETRYABLE_STATUS_CODES

    return True


def _make_retrier(max_tries=10) -> Callable[[Callable[P, T]], Callable[P, T]]:
    return backoff.on_exception(
        backoff.expo,
        requests.exceptions.RequestException,
        giveup=_fatal_request_error,
        max_tries=max_tries,
        jitter=lambda wait: random.uniform(0.8 * wait, 1.2 * wait),
        factor=10,
    )


def download_granule(
    maap: MAAP,
    todir: str,
    granule: Granule,
    *,
    max_tries=10,
) -> str | Never:
    """Download a granule's data file.

    Automatically fetch S3 credentials appropriate for `granule`, based upon
    it's S3 URL, and automatically refreshes credentials before expiry.

    Parameters
    ----------
    maap
        The MAAP client to use for downloading the granule.
    todir
        The directory to which to download the granule.
    granule
        The metadata for the granule to download.

    Returns
    -------
    dest
        The absolute path of the downloaded file.

    Raises
    ------
    ValueError
        If the granule is not configured with a download URL.
    """
    granule_ur = granule["Granule"]["GranuleUR"]
    download_url = granule.getDownloadUrl() or ""
    logger.debug(f"Downloading granule {granule_ur} from {download_url} to {todir}")

    if download_url.startswith("s3"):
        if endpoint := _s3_credentials_endpoint(granule):
            _setup_default_boto3_session(_s3_credentials(maap, endpoint))

    retry_get_data = _make_retrier(max_tries)(granule.getData)

    if dest := retry_get_data(todir):
        return dest

    raise ValueError(f"granule {granule_ur} is not configured with a download URL")


def find_collection(
    maap: MAAP,
    cmr_host: str,
    params: Mapping[str, str],
) -> IOResultE[Collection]:
    """Find a collection matching search parameters.

    Return `IOSuccess[Collection]` containing the collection upon successful
    search; otherwise return `IOFailure[Exception]` containing the reason for
    failure, which is a `ValueError` when there is no matching collection.
    """
    not_found_error = ValueError(f"No collection found at {cmr_host}: {params}")

    return flow(
        impure_safe(maap.searchCollection)(cmr_host=cmr_host, limit=1, **params),
        bind_result(
            pipe(
                safe(operator.itemgetter(0)),
                lash(fp.always(Failure(not_found_error))),
            )
        ),
    )
