"""Functions providing convenience and safety for maap-py classes and methods.

Collection functions:

- find_collection attempts to find a single collection

Granule functions:

- download_granule attempts to download a granule file
"""

import logging
import operator
from typing import TYPE_CHECKING, Mapping, Union

import boto3
from cachetools import FIFOCache, cached
from cachetools.func import ttl_cache
from maap.maap import MAAP
from maap.Result import Collection, Granule
from returns.converters import result_to_maybe
from returns.curry import partial
from returns.io import IOResult, IOResultE, impure_safe
from returns.maybe import Maybe
from returns.pipeline import flow, is_successful, pipe
from returns.pointfree import bind, bind_result, lash, map_
from returns.result import Failure, safe

from gedi_subset import fp

if TYPE_CHECKING:
    from maap.AWS import AWSCredentials

logger = logging.getLogger(f"gedi_subset.{__name__}")


def _is_s3_credentials_online_resource(resource) -> bool:
    url = resource.get("URL", "").lower()
    description = resource.get("Description", "").lower()

    # TODO: is this sufficient for identifying URL for obtaining S3 credentials?
    return url and url.endswith("/s3credentials") or "credentials" in description


def _s3_credentials_endpoint(granule: Granule) -> Maybe[str]:
    return flow(
        granule.get("Granule", {}).get("OnlineResources", {}).get("OnlineResource", []),
        lambda resources: resources if isinstance(resources, list) else [resources],
        fp.find(_is_s3_credentials_online_resource),
        bind(safe(operator.itemgetter("URL"))),
        result_to_maybe,
    )


@ttl_cache(ttl=55 * 60)
def _earthdata_s3_credentials(maap: MAAP, endpoint: str) -> IOResultE["AWSCredentials"]:
    """Returns short-term AWS credentials obtained from an S3 credentials endpoint."""

    logger.debug(f"Obtaining S3 credentials from {endpoint}")

    return impure_safe(maap.aws.earthdata_s3_credentials)(endpoint)


@cached(cache=FIFOCache(maxsize=1), key=lambda creds: creds["sessionToken"])
def _setup_default_boto3_session(creds: "AWSCredentials") -> None:
    """Sets up the default boto3 session using the specified credentials."""

    logger.debug("Setting up default boto3 session with new credentials")

    boto3.setup_default_session(
        aws_access_key_id=creds["accessKeyId"],
        aws_secret_access_key=creds["secretAccessKey"],
        aws_session_token=creds["sessionToken"],
        # TODO: make this configurable
        region_name="us-west-2",
    )


def download_granule(maap: MAAP, todir: str, granule: Granule) -> IOResultE[str]:
    """Download a granule's data file.

    Automatically fetch S3 credentials appropriate for `granule`, based upon
    it's S3 URL, and automatically refreshes credentials before expiry.

    Return `IOSuccess[str]` containing the absolute path of the downloaded file
    upon success; otherwise return `IOFailure[Exception]` containing the reason
    for failure.
    """
    granule_ur = granule["Granule"]["GranuleUR"]
    download_url = granule.getDownloadUrl()
    logger.debug(f"Downloading granule {granule_ur} to directory {todir}")

    if download_url and download_url.startswith("s3"):
        result: Union[Maybe, IOResultE] = flow(
            _s3_credentials_endpoint(granule),
            bind(partial(_earthdata_s3_credentials, maap)),
            map_(_setup_default_boto3_session),
        )

        # If result is an IOResult, that means the granule has an S3 credentials
        # endpoint, and an attempt was made to obtain S3 credentials.  If the
        # attempt was unsuccessful, return the failure rather than proceeding to
        # download the granule.
        if isinstance(result, IOResult) and not is_successful(result):
            return result

    return impure_safe(granule.getData)(todir)


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
