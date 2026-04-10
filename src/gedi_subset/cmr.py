from typing import Mapping

from maap.Result import Collection

from gedi_subset.maapx import find_collection
from maap.maap import MAAP


def s3_credentials_api_endpoint(c: Collection) -> str:
    """Return the AWS S3 credentials endpoint for a CMR Collection."""
    return c["Collection"]["DirectDistributionInformation"]["S3CredentialsAPIEndpoint"]


def is_gedi_collection(c: Collection) -> bool:
    """Return True if the specified collection is a GEDI collection containing granule
    data files in HDF5 format; False otherwise."""

    c = c.get("Collection", {})
    attrs = c.get("AdditionalAttributes", {}).get("AdditionalAttribute", [])
    data_format_attrs = (attr for attr in attrs if attr.get("Name") == "Data Format")
    data_format = next(data_format_attrs, {"Value": c.get("DataFormat")}).get("Value")

    return c.get("ShortName", "").startswith("GEDI") and data_format == "HDF5"


def find_gedi_collection(maap: MAAP, params: Mapping[str, str]) -> Collection:
    """Find a GEDI collection matching search parameters.

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
        First GEDI collection that matches the search parameters.

    Raises
    ------
    ValueError
        If the query failed, no GEDI collection was found, or multiple collections were
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
    if not is_gedi_collection(collection := find_collection(maap, params)):
        raise ValueError(
            f"Collection {collection['Collection']['ShortName']} is not a GEDI"
            " collection, or does not contain HDF5 data files."
        )

    return collection
