import pytest
from maap.maap import MAAP

from gedi_subset.maapx import find_collection


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
