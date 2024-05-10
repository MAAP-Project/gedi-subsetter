#!/usr/bin/env -S python -W ignore::FutureWarning -W ignore::UserWarning

import logging
import multiprocessing
import os
import os.path
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, NoReturn, Optional, Sequence, Tuple

import geopandas as gpd
import h5py
import s3fs
import typer
from maap.maap import MAAP
from maap.Result import Collection, Granule
from returns.curry import partial
from returns.functions import raise_exception, tap
from returns.io import IOFailure, IOResult, IOResultE, IOSuccess, impure_safe
from returns.iterables import Fold
from returns.maybe import Maybe, Nothing, Some
from returns.pipeline import flow, is_successful, pipe
from returns.pointfree import bind, bind_ioresult, lash, map_
from returns.unsafe import unsafe_perform_io

import gedi_subset.fp as fp
from gedi_subset import osx
from gedi_subset.gedi_utils import (
    beam_filter_from_names,
    chext,
    gdf_read_parquet,
    gdf_to_file,
    gdf_to_parquet,
    granule_intersects,
    is_coverage_beam,
    is_power_beam,
    subset_hdf5,
)
from gedi_subset.maapx import find_collection

logical_dois = {
    "L1B": "10.5067/GEDI/GEDI01_B.002",
    "L2A": "10.5067/GEDI/GEDI02_A.002",
    "L2B": "10.5067/GEDI/GEDI02_B.002",
    "L4A": "10.3334/ORNLDAAC/2056",
}

DEFAULT_LIMIT = 1_000

LOGGING_FORMAT = "%(asctime)s [%(processName)s:%(name)s] [%(levelname)s] %(message)s"

logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
logging.Formatter.converter = time.gmtime
logging.Formatter.default_time_format = "%Y-%m-%dT%H:%M:%S"
logging.Formatter.default_msec_format = "%s,%03dZ"

logger = logging.getLogger("gedi_subset")


@dataclass
class SubsetGranuleProps:
    """Properties for calling `subset_granule` with a single argument.

    Since `multiprocessing.Pool.imap_unordered` does not support supplying
    multiple iterators (like `builtins.map` does) for producing muliple
    arguments to the supplied function, we must package all "arguments" into a
    single argument.
    """

    fs: s3fs.S3FileSystem
    granule: Granule
    maap: MAAP
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


def find_gedi_collection(
    maap: MAAP, params: Mapping[str, str]
) -> IOResultE[Collection]:
    """Find a GEDI collection matching the given parameters.

    Return `IOSuccess[Collection]` containing the collection upon successful
    search; otherwise return `IOFailure[Exception]` containing the reason for
    failure, which is a `ValueError` when there is no matching collection or
    the collection is _not_ a GEDI collection.
    """
    return (
        IOSuccess(c)
        if is_gedi_collection(c := find_collection(maap, params))
        else IOFailure(
            ValueError(
                f"Collection {c['Collection']['ShortName']} is not a GEDI"
                " collection, or does not contain HDF5 data files."
            )
        )
    )


def beam_filter(beams: str) -> Callable[[h5py.Group], bool]:
    if beams.upper() == "COVERAGE":
        return is_coverage_beam
    if beams.upper() == "POWER":
        return is_power_beam
    if beams.upper() == "ALL":
        return fp.always(True)
    return beam_filter_from_names([item.strip() for item in beams.split(",")])


def check_beams_option(value: str) -> str | NoReturn:
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


def subset_granule(props: SubsetGranuleProps) -> IOResultE[Maybe[str]]:
    """Subset a granule to a GeoParquet file and return the output path.

    Download the specified granule (`props.granule`) obtained from a CMR search
    to the specified directory (`props.output_dir`), subset it to a GeoParquet
    file where it overlaps with the specified AOI (`props.aoi_gdf`), remove the
    downloaded granule file, and return the path to the output file.

    Return `Nothing` if the subset is empty or if an error occurred attempting
    to read the granule file (in which case, the offending file is retained in
    order to facilitate analysis).  In either case, no GeoParquet file is
    written; otherwise return `Some[str]` indicating the output path of the
    GeoParquet file.
    """

    if not (inpath := props.granule.getDownloadUrl()):
        granule_ur = props.granule["Granule"]["GranuleUR"]
        logger.warning(f"Skipping granule {granule_ur} [no download URL]")
        return IOSuccess(Nothing)

    logger.debug(f"Subsetting {inpath}")

    try:
        with (
            props.fs.open(inpath, block_size=4 * 1024 * 1024, cache_type="all") as f,
            h5py.File(f) as hdf5,
        ):
            gdf = subset_hdf5(
                hdf5,
                aoi=props.aoi_gdf,
                lat_col=props.lat_col,
                lon_col=props.lon_col,
                beam_filter=beam_filter(props.beams),
                columns=props.columns,
                query=props.query,
            )
    except Exception as e:
        granule_ur = props.granule["Granule"]["GranuleUR"]
        logger.warning(f"Skipping granule {granule_ur} [failed to read {inpath}: {e}]")
        logger.exception(e)
        return IOSuccess(Nothing)

    if gdf.empty:
        logger.debug(f"Empty subset produced from {inpath}; not writing")
        return IOSuccess(Nothing)

    outpath = chext(".gpq", os.path.join(props.output_dir, inpath.split("/")[-1]))
    logger.debug(f"Writing subset to {outpath}")

    return gdf_to_parquet(outpath, gdf).map(fp.always(Some(outpath)))


def init_process(logging_level: int) -> None:
    set_logging_level(logging_level)


def set_logging_level(logging_level: int) -> None:
    global logger
    logger.setLevel(logging_level)


def subset_granules(
    maap: MAAP,
    aoi_gdf: gpd.GeoDataFrame,
    lat: str,
    lon: str,
    beams: str,
    columns: Sequence[str],
    query: Optional[str],
    output_dir: Path,
    dest: Path,
    init_args: Tuple[Any, ...],
    granules: Iterable[Granule],
) -> IOResultE[Tuple[str, ...]]:
    def subset_saved(path: IOResultE[Maybe[str]]) -> bool:
        """Return `True` if `path`'s value is a `Some`, otherwise `False` if it
        is `Nothing`.  This indicates whether or not a subset file was written
        (and thus whether or not the subset was empty).
        """
        return unsafe_perform_io(path.map(is_successful).value_or(False))

    def append_subset(src: str) -> IOResultE[str]:
        to_file_props = dict(index=False, mode="a", driver="GPKG")
        logger.debug(f"Appending {src} to {dest}")

        return flow(
            gdf_read_parquet(src),
            bind_ioresult(partial(gdf_to_file, dest, to_file_props)),
            tap(pipe(fp.always(src), osx.remove)),
            map_(fp.always(src)),
        )

    # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.pool.Pool.imap
    # We're dealing with relatively small numbers of granules (dozens, perhaps
    # hundreds, at most), so we can stick with a chunksize of 1.
    chunksize = 1
    processes = min(8, os.cpu_count() or 32)
    found_granules = list(granules)
    # On occasion, a granule is missing a download URL, so the _downloadname
    # attribute is set to None, and attempting to download it throws an
    # exception, so we just skip such granules to avoid failing.
    downloadable_granules = [
        granule for granule in found_granules if granule._downloadname
    ]

    logger.info(f"Found {len(found_granules)} in the CMR")
    logger.info(f"Total downloadable granules: {len(downloadable_granules)}")

    fs = s3fs.S3FileSystem()
    payloads = (
        SubsetGranuleProps(
            fs, granule, maap, aoi_gdf, lat, lon, beams, columns, query, output_dir
        )
        for granule in downloadable_granules
    )

    logger.info(f"Subsetting on {processes} processes (chunksize={chunksize})")

    with multiprocessing.Pool(processes, init_process, init_args) as pool:
        return flow(
            pool.imap_unordered(subset_granule, payloads, chunksize),
            fp.filter(subset_saved),  # Skip granules that produced empty subsets
            fp.map(bind(bind(append_subset))),  # Append non-empty subset # type: ignore
            partial(Fold.collect, acc=IOSuccess(())),
            lash(raise_exception),  # Fail fast (if subsetting errored out)
        )


def main(
    aoi: Path = typer.Option(
        ...,
        help="Area of Interest (path to GeoJSON file)",
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
    ),
    doi=typer.Option(
        ...,
        callback=lambda value: logical_dois.get(value.upper(), value),
        help=(
            "Digital Object Identifier (DOI) of collection to subset"
            " (https://www.doi.org/), or one of these logical, case-insensitive"
            f" names: {', '.join(logical_dois)}"
        ),
    ),
    lat: str = typer.Option(
        ..., help=("Latitude dataset used in the geometry of the dataframe")
    ),
    lon: str = typer.Option(
        ..., help=("Longitude dataset used in the geometry of the dataframe")
    ),
    beams: str = typer.Option(
        "all",
        callback=check_beams_option,
        help=(
            "Which beams to include in the subset. Must be 'all', 'coverage', 'power',"
            " OR a comma-separated list of beam names, with or without the 'BEAM'"
            " prefix (e.g., 'BEAM0000,BEAM0001' or '0000,0001')"
        ),
    ),
    columns: str = typer.Option(
        ...,
        help="Comma-separated list of columns to select",
    ),
    query: str = typer.Option(
        None,
        help="Boolean query expression to select rows",
    ),
    limit: int = typer.Option(
        DEFAULT_LIMIT,
        callback=lambda value: DEFAULT_LIMIT if value < 1 else value,
        help="Maximum number of granules to subset",
    ),
    temporal: str = typer.Option(
        None,
        help=(
            "Temporal range to subset"
            " (e.g., '2019-01-01T00:00:00Z,2020-01-01T00:00:00Z')"
        ),
    ),
    output: Path = typer.Option(
        None,
        "-o",
        "--output",
        help="Output file path for generated subset file",
        exists=False,
        file_okay=True,
        dir_okay=False,
        writable=True,
        readable=True,
    ),
    verbose: bool = typer.Option(False, help="Provide verbose output"),
) -> None:
    logging_level = logging.DEBUG if verbose else logging.INFO
    set_logging_level(logging_level)

    dest = (
        ("output" / (output or Path(f"{aoi.stem}_subset")))
        .with_suffix(".gpkg")
        .absolute()
    )
    output_dir = dest.parent
    os.makedirs(output_dir, exist_ok=True)

    # Remove existing combined subset file, primarily to support
    # testing.  When running in the context of a DPS job, there
    # should be no existing file since every job uses a unique
    # output directory.
    osx.remove(f"{dest}")

    maap = MAAP("api.maap-project.org")
    cmr_host = "cmr.earthdata.nasa.gov"

    IOResult.do(
        subsets
        for aoi_gdf in impure_safe(gpd.read_file)(aoi)
        # Use wildcards around DOI value because some collections have incorrect
        # DOI values. For example, the L2B collection has the full DOI URL as
        # the DOI value (i.e., https://doi.org/<DOI> rather than just <DOI>).
        for collection in find_gedi_collection(
            maap, dict(cmr_host=cmr_host, doi=f"*{doi}*", cloud_hosted="true")
        )
        for granules in impure_safe(maap.searchGranule)(
            cmr_host=cmr_host,
            collection_concept_id=collection["concept-id"],
            bounding_box=",".join(fp.map(str)(aoi_gdf.total_bounds)),  # pyright: ignore
            limit=limit,
            **(dict(temporal=temporal) if temporal else {}),
        )
        for subsets in subset_granules(
            maap,
            aoi_gdf,
            lat,
            lon,
            beams,
            [c.strip() for c in columns.split(",")],
            query,
            output_dir,
            dest,
            (logging_level,),
            fp.filter(granule_intersects(aoi_gdf.unary_union))(granules),
        )
    ).bind_ioresult(
        lambda subsets: (
            IOSuccess(subsets)
            if subsets
            else IOFailure(ValueError(f"No granules intersect the AOI: {aoi}"))
        )
    ).map(
        lambda subsets: logger.info(f"Subset {len(subsets)} granule(s) to {dest}")
    ).alt(
        raise_exception
    )


if __name__ == "__main__":
    typer.run(main)
