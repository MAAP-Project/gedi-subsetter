"""Functions providing convenience and safety for maap-py classes and methods.

Collection functions:

- `find_collection` attempts to find a single collection

Granule functions:

- `download_granule` attempts to download a granule file
"""

import logging
from typing import Mapping, ParamSpec, TypeVar

from maap.maap import MAAP
from maap.Result import Collection, Granule

logger = logging.getLogger(__name__)


__all__ = [
    "download_granule",
    "find_collection",
]

T = TypeVar("T")
P = ParamSpec("P")


def download_granule(granule: Granule, todir: str) -> str:
    """Download a granule's data file.

    Parameters
    ----------
    todir
        Directory to which to download the granule.
    granule
        Metadata for the granule to download.

    Returns
    -------
    dest
        Absolute path of the downloaded file.

    Raises
    ------
    ValueError
        If the granule is not configured with a download URL.
    """
    granule_ur = granule["Granule"]["GranuleUR"]

    if not (download_url := granule.getDownloadUrl()):
        raise ValueError(f"granule {granule_ur} does not have a download URL")

    logger.debug(f"Downloading granule {granule_ur} from {download_url} to {todir}")

    if dest := granule.getData(todir):
        return dest

    raise ValueError(
        f"failed to download granule {granule_ur} from {download_url} to {todir}"
    )


def find_collection(maap: MAAP, params: Mapping[str, str]) -> Collection:
    """Find a collection matching search parameters.

    Parameters
    ----------
    maap
        MAAP client to use for searching for the collection.
    params
        Search parameters to use when searching for the collection.  For
        available search parameters, see the
        [CMR Search API documentation](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html). # noqa: E501

    Returns
    -------
    collection
        First collection that matches the search parameters.

    Raises
    ------
    ValueError
        If the query failed, no collection was found, or multiple collections were
        found.

    Examples
    --------
    >>> maap = MAAP("api.maap-project.org")
    >>> find_collection(
    ...     maap, {"cloud_hosted": "true", "doi": "10.3334/ORNLDAAC/2056"}
    ... )  # doctest: +SKIP
    {'concept-id': 'C2237824918-ORNL_CLOUD', 'revision-id': '28',
     'format': 'application/echo10+xml',
     'Collection': {'ShortName': 'GEDI_L4A_AGB_Density_V2_1_2056', ...}}
    """
    # Set limit=2 simply to catch the case where multiple collections are found, but
    # without having to fetch a larger response.
    if not (collections := maap.searchCollection(limit=2, **params)):
        raise ValueError(f"No collection found for: {params}")
    if len(collections) > 1:
        raise ValueError(f"Multiple collections found for: {params}")

    return collections[0]
