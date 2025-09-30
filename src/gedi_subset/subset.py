#!/usr/bin/env -S python -W ignore::FutureWarning -W ignore::UserWarning

import json
import logging
import multiprocessing
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Callable,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    cast,
)

import fsspec
import geopandas as gpd
import h5py
import typer
from maap.maap import MAAP
from maap.Result import Collection

import gedi_subset.fp as fp
from gedi_subset.gedi_utils import (
    beam_filter_from_names,
    concat_parquet_files,
    granule_intersects,
    is_coverage_beam,
    is_power_beam,
    subset_hdf5,
)
from gedi_subset.maapx import find_collection

logical_dois = {
    "L1B": "C2142749196-LPCLOUD",  # DOI: 10.5067/GEDI/GEDI01_B.002
    "L2A": "C2142771958-LPCLOUD",  # DOI: 10.5067/GEDI/GEDI02_A.002
    "L2B": "C2142776747-LPCLOUD",  # DOI: 10.5067/GEDI/GEDI02_B.002
    "L4A": "C2237824918-ORNL_CLOUD",  # DOI: 10.3334/ORNLDAAC/2056
    "L4C": "C3049900163-ORNL_CLOUD",  # DOI: 10.3334/ORNLDAAC/2338
}

DEFAULT_LIMIT = 100_000
DEFAULT_TOLERATED_FAILURE_PERCENTAGE = 0

LOGGING_FORMAT = "%(asctime)s [%(processName)s:%(name)s] [%(levelname)s] %(message)s"

logging.basicConfig(level=logging.WARN, format=LOGGING_FORMAT)
logging.Formatter.converter = time.gmtime
logging.Formatter.default_time_format = "%Y-%m-%dT%H:%M:%S"
logging.Formatter.default_msec_format = "%s,%03dZ"

logger = logging.getLogger("gedi_subset")


@dataclass(frozen=True, kw_only=True)
class SubsetGranuleProps:
    """Properties for calling `subset_granule` with a single argument.

    Since `multiprocessing.Pool.imap_unordered` does not support supplying
    multiple iterators (like `builtins.map` does) for producing muliple
    arguments to the supplied function, we must package all "arguments" into a
    single argument.
    """

    fsspec_kwargs: Mapping[str, Any] = field(default_factory=dict)
    granule_url: str
    aoi_gdf: gpd.GeoDataFrame
    lat_col: str
    lon_col: str
    beams: str
    columns: Sequence[str]
    query: Optional[str]
    output_dir: Path


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


def beam_filter(beams: str) -> Callable[[h5py.Group], bool]:
    if beams.upper() == "COVERAGE":
        return is_coverage_beam
    if beams.upper() == "POWER":
        return is_power_beam
    if beams.upper() == "ALL":
        return lambda _: True
    return beam_filter_from_names([item.strip() for item in beams.split(",")])


def check_beams_option(value: str) -> str:
    upper_value = value.upper()
    suffixes = [name.strip().lstrip("BEAM") for name in upper_value.split(",")]
    valid_suffixes = ["0000", "0001", "0010", "0011", "0101", "0110", "1000", "1011"]

    if upper_value not in ["ALL", "COVERAGE", "POWER"] and any(
        suffix not in valid_suffixes for suffix in suffixes
    ):
        raise typer.BadParameter(value)

    return (
        ",".join(f"BEAM{suffix}" for suffix in suffixes)
        if len(suffixes) > 1
        else upper_value
    )


def subset_granule(props: SubsetGranuleProps) -> Path | None | Exception:
    """Subset a granule to a GeoParquet file.

    Subset the specified granule (`props.granule_url`) to a GeoParquet file
    where it overlaps with the specified AOI (`props.aoi_gdf`) and return the
    path to the output file, or return `None` if the subset is empty.

    Returns
    -------
    Path | None
        Absolute path to output file, if subset is non-empty; otherwise, `None`.
    """

    granule_url = props.granule_url
    logger.debug("Subsetting %s", granule_url)
    fsspec_kwargs = {
        "default_cache_type": "mmap",
        "default_block_size": 5 * 1024 * 1024,  # fsspec default is 5 MB
        "default_fill_cache": True,
        "requester_pays": True,
        # Allow the caller to override the default values above.
        **props.fsspec_kwargs,
    }

    fs: fsspec.AbstractFileSystem
    urlpath: str
    fs, urlpath = fsspec.url_to_fs(granule_url, **fsspec_kwargs)

    with fs.open(urlpath, mode="rb") as f, h5py.File(f) as hdf5:
        gdf = fp.safely(
            subset_hdf5,
            hdf5,
            aoi=props.aoi_gdf,
            lat_col=props.lat_col,
            lon_col=props.lon_col,
            beam_filter=beam_filter(props.beams),
            columns=props.columns,
            query=props.query,
        )

        if isinstance(gdf, Exception):
            return gdf

        if isinstance(f, fsspec.spec.AbstractBufferedFile) and (cache := f.cache):
            stats = ", ".join(
                [
                    f"{cache.blocksize} bytes per block",
                    f"{cache.nblocks} blocks",
                    f"{cache.hit_count} hits",
                    f"{cache.miss_count} misses",
                    f"{cache.size} bytes in file",
                    f"{cache.total_requested_bytes} requested bytes",
                ]
            )
            logger.debug("fsspec cache '%s' for '%s': %s", cache.name, urlpath, stats)

    if gdf.empty:
        logger.debug("Empty subset produced from %s; not writing", granule_url)
        return None

    outpath = (props.output_dir / granule_url.split("/")[-1]).with_suffix(".parquet")
    logger.debug("Writing subset to %s", outpath)

    return err if (err := fp.safely(gdf.to_parquet, outpath)) else outpath


def init_process(logging_level: int) -> None:
    set_logging_level(logging_level)


def set_logging_level(logging_level: int) -> None:
    global logger
    logger.setLevel(logging_level)


def make_error_tracker[T](max_errors: int) -> Callable[[T], T]:
    n_errors = 0

    def track_error(value: T) -> T:
        nonlocal n_errors

        if isinstance(value, Exception) and (n_errors := n_errors + 1) > max_errors:
            raise value

        return value

    return track_error


def subset_granules(
    aoi_gdf: gpd.GeoDataFrame,
    lat: str,
    lon: str,
    beams: str,
    columns: Sequence[str],
    query: Optional[str],
    output_dir: Path,
    dest: Path,
    init_args: Tuple[Any, ...],
    granule_urls: Sequence[str],
    fsspec_kwargs: Optional[Mapping[str, Any]] = None,
    processes: Optional[int] = None,
    tolerated_failure_percentage: int = DEFAULT_TOLERATED_FAILURE_PERCENTAGE,
) -> tuple[Path, ...]:
    max_errors = len(granule_urls) * tolerated_failure_percentage // 100
    track_error = make_error_tracker(max_errors)
    payloads = (
        SubsetGranuleProps(
            fsspec_kwargs=fsspec_kwargs or {},
            granule_url=granule_url,
            aoi_gdf=aoi_gdf,
            lat_col=lat,
            lon_col=lon,
            beams=beams,
            columns=columns,
            query=query,
            output_dir=output_dir,
        )
        for granule_url in granule_urls
    )

    logger.info(f"Subsetting on {processes} CPUs")

    with multiprocessing.get_context("spawn").Pool(
        processes, init_process, init_args
    ) as pool:
        files = tuple(
            file
            for result in pool.imap_unordered(subset_granule, payloads)
            if isinstance(file := track_error(result), Path)
        )

    if files:
        concat_parquet_files(files, dest)

    return files


def cli(
    aoi: Annotated[
        Path,
        typer.Option(
            show_default=False,
            help="Area of Interest (path to GeoJSON file)",
            exists=True,
            file_okay=True,
            dir_okay=False,
            writable=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    doi: Annotated[
        str,
        typer.Option(
            show_default=False,
            callback=lambda value: logical_dois.get(value.upper(), value.upper()),
            help=(
                "Digital Object Identifier (DOI) or Concept ID of collection to subset"
                " (https://www.doi.org/), or one of these logical, case-insensitive"
                f" names: {', '.join(logical_dois)}"
            ),
        ),
    ],
    lat: Annotated[
        str,
        typer.Option(
            show_default=False,
            help=("Latitude dataset used in the geometry of the dataframe"),
        ),
    ],
    lon: Annotated[
        str,
        typer.Option(
            show_default=False,
            help=("Longitude dataset used in the geometry of the dataframe"),
        ),
    ],
    columns: Annotated[
        str,
        typer.Option(
            show_default=False,
            help="Comma-separated list of columns to select",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            ...,
            "-o",
            "--output",
            help="Output file path for generated subset file",
            exists=False,
            file_okay=True,
            dir_okay=True,
            writable=True,
            readable=True,
        ),
    ],
    beams: Annotated[
        str,
        typer.Option(
            callback=check_beams_option,
            help=(
                "Which beams to include in the subset.  Must be 'all', 'coverage',"
                " 'power', OR a comma-separated list of beam names, with or without the"
                " 'BEAM' prefix (e.g., 'BEAM0000,BEAM0001' or '0000,0001')"
            ),
        ),
    ] = "all",
    query: Annotated[
        Optional[str],
        typer.Option(help="Boolean query expression to select rows"),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(
            callback=lambda value: DEFAULT_LIMIT if value < 1 else value,
            help="Maximum number of granules to subset",
        ),
    ] = DEFAULT_LIMIT,
    temporal: Annotated[
        Optional[str],
        typer.Option(
            help=(
                "Temporal range to subset"
                " (e.g., '2019-01-01T00:00:00Z,2020-01-01T00:00:00Z')"
            ),
        ),
    ] = None,
    verbose: Annotated[bool, typer.Option(help="Provide verbose output")] = False,
    tolerated_failure_percentage: Annotated[
        int,
        typer.Option(
            min=0,
            max=100,
            help=(
                "Integral percentage of individual granule subset failures"
                " tolerated before failing the job"
            ),
        ),
    ] = DEFAULT_TOLERATED_FAILURE_PERCENTAGE,
    fsspec_kwargs: Annotated[
        Optional[dict[str, Any]],
        typer.Option(
            parser=lambda value: json.loads(value) if isinstance(value, str) else value,
            metavar="JSON",
            help=(
                "Keyword arguments (as JSON object) to pass to fsspec.url_to_fs"
                " for reading HDF5 files"
            ),
        ),
    ] = None,
    processes: Annotated[
        int, typer.Option(help="Number of processes to use for parallel processing")
    ] = (os.cpu_count() or 1),
) -> None:
    logging_level = logging.DEBUG if verbose else logging.INFO
    set_logging_level(logging_level)

    dest = (
        output / Path(f"{aoi.stem}_subset.gpkg") if output.is_dir() else output
    ).absolute()
    output_dir = dest.parent
    os.makedirs(output_dir, exist_ok=True)

    # Remove existing combined subset file, primarily to support
    # testing.  When running in the context of a DPS job, there
    # should be no existing file since every job uses a unique
    # output directory.
    dest.unlink(missing_ok=True)

    maap = MAAP()
    cmr_host = "cmr.earthdata.nasa.gov"

    aoi_gdf = cast(gpd.GeoDataFrame, gpd.read_file(aoi))
    aoi_geometry = aoi_gdf.union_all()
    collection_concept_id = (
        doi
        # Assume `doi` value is actually a collection concept ID, and thus avoid
        # a search for the collection, since all we need is the concept ID.
        if doi.startswith("C")
        # Otherwise, search for collection by DOI so we can get its concept ID.
        else find_gedi_collection(
            maap, dict(cmr_host=cmr_host, doi=doi, cloud_hosted="true")
        )["concept-id"]
    )
    granule_urls = tuple(
        url
        for granule in maap.searchGranule(
            cmr_host=cmr_host,
            collection_concept_id=collection_concept_id,
            bounding_box=",".join(map(str, aoi_gdf.total_bounds)),
            limit=limit,
            **(dict(temporal=temporal) if temporal else {}),
        )
        if granule._downloadname
        and granule_intersects(aoi_geometry, granule)
        and (url := granule.getDownloadUrl())
    )

    if not granule_urls:
        logger.info("No granules intersect the AOI within the temporal range.")
    elif paths := subset_granules(
        aoi_gdf,
        lat,
        lon,
        beams,
        [c.strip() for c in columns.split(",")],
        query,
        output_dir,
        dest,
        (logging_level,),
        granule_urls,
        fsspec_kwargs,
        processes,
        tolerated_failure_percentage,
    ):
        logger.info(f"Subset {len(paths)} granule(s) to {dest}.")
    else:
        logger.info(f"Empty subset: no rows satisfy the query {query!r}")


def main():
    typer.run(cli)


if __name__ == "__main__":
    main()
