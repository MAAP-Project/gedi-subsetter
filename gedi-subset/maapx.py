import logging
import operator
from typing import Mapping, TYPE_CHECKING

import boto3
from cachetools import cached, FIFOCache
from cachetools.func import ttl_cache
from maap.maap import MAAP
from maap.Result import Collection, Granule
from returns.curry import partial
from returns.functions import tap
from returns.io import IOFailure, IOResultE, impure_safe
from returns.maybe import Maybe, Nothing, Some, maybe
from returns.pipeline import flow
from returns.pointfree import bind, bind_ioresult, bind_result, lash, map_
from returns.result import safe

from fp import K

if TYPE_CHECKING:
    from maap.AWS import AWSCredentials

logger = logging.getLogger(f"gedi_subset.{__name__}")


# https://nasa-openscapes.github.io/2021-Cloud-Workshop-AGU/how-tos/Earthdata_Cloud__Single_File__Direct_S3_Access_COG_Example.html
_S3_CREDENTIALS_ENDPOINT_BY_DAAC: Mapping[str, str] = dict(
    po="https://archive.podaac.earthdata.nasa.gov/s3credentials",
    gesdisc="https://data.gesdisc.earthdata.nasa.gov/s3credentials",
    lp="https://data.lpdaac.earthdatacloud.nasa.gov/s3credentials",
    ornl="https://data.ornldaac.earthdata.nasa.gov/s3credentials",
    ghrc="https://data.ghrc.earthdata.nasa.gov/s3credentials",
)


def _s3_credentials_endpoint(download_url: str) -> Maybe[str]:
    endpoints = [
        endpoint
        for key, endpoint in _S3_CREDENTIALS_ENDPOINT_BY_DAAC.items()
        if key in download_url
    ]

    return Some(endpoints[0]) if endpoints else Nothing


@ttl_cache(ttl=55 * 60)
def _earthdata_s3_credentials(maap: MAAP, endpoint: str) -> IOResultE["AWSCredentials"]:
    """Returns short-term AWS credentials obtained from an S3 credentials endpoint."""

    logger.debug(f"Obtaining S3 credentials from {endpoint}")

    return impure_safe(maap.aws.earthdata_s3_credentials)(endpoint)


@cached(cache=FIFOCache(maxsize=1), key=lambda creds: creds["sessionToken"])
def _setup_default_boto3_session(creds: "AWSCredentials") -> boto3.session.Session:
    """Sets up the default boto3 session using the specified credentials."""

    logger.debug("Setting up default boto3 session with new credentials")

    return boto3.setup_default_session(
        aws_access_key_id=creds["accessKeyId"],
        aws_secret_access_key=creds["secretAccessKey"],
        aws_session_token=creds["sessionToken"],
        region_name="us-west-2",
    )


def download_granule(maap: MAAP, todir: str, granule: Granule) -> IOResultE[str]:
    """Downloads a granule's data file."""
    ur: str = granule["Granule"]["GranuleUR"]

    flow(
        maybe(granule.getDownloadUrl)(),
        lash(K(IOFailure(ValueError(f"Missing download URL for granule {ur}")))),
        bind(_s3_credentials_endpoint),
        bind(partial(_earthdata_s3_credentials, maap)),
        map_(_setup_default_boto3_session),
    )

    logger.debug(f"Downloading granule {ur} to directory {todir}")

    return impure_safe(granule.getData)(todir)


def find_collection(
    maap: MAAP,
    cmr_host: str,
    params: Mapping[str, str],
) -> IOResultE[Collection]:
    return flow(
        impure_safe(maap.searchCollection)(cmr_host=cmr_host, **dict(params, limit=1)),
        bind_result(safe(operator.itemgetter(0))),
        lash(K(IOFailure(ValueError(f"No collection found at {cmr_host}: {params}")))),
    )
