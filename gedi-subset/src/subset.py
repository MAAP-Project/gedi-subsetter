#!/usr/bin/env -S python -W ignore::FutureWarning -W ignore::UserWarning

import logging
import multiprocessing
import os
import os.path
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Sequence, Tuple

import geopandas as gpd
import typer
from maap.maap import MAAP
from maap.Result import Granule
from returns.curry import partial
from returns.functions import raise_exception, tap
from returns.io import IOFailure, IOResult, IOResultE, IOSuccess, impure_safe
from returns.iterables import Fold
from returns.maybe import Maybe, Nothing, Some
from returns.pipeline import flow, is_successful, pipe
from returns.pointfree import bind, bind_ioresult, lash, map_
from returns.unsafe import unsafe_perform_io

import osx
from fp import always, filter, map
from gedi_utils import (
    chext,
    df_assign,
    gdf_read_parquet,
    gdf_to_file,
    gdf_to_parquet,
    granule_intersects,
    subset_hdf5,
)
from maapx import download_granule, find_collection


class CMRHost(str, Enum):
    maap = "cmr.maap-project.org"
    nasa = "cmr.earthdata.nasa.gov"


LOGGING_FORMAT = "%(asctime)s [%(processName)s:%(name)s] [%(levelname)s] %(message)s"

logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
logger = logging.getLogger("gedi_subset")


@dataclass
class SubsetGranuleProps:
    """Properties for calling `subset_granule` with a single argument.

    Since `multiprocessing.Pool.imap_unordered` does not support supplying
    multiple iterators (like `builtins.map` does) for producing muliple
    arguments to the supplied function, we must package all "arguments" into a
    single argument.
    """

    granule: Granule
    maap: MAAP
    aoi_gdf: gpd.GeoDataFrame
    columns: Sequence[str]
    query: str
    output_dir: Path


@impure_safe
def subset_granule(props: SubsetGranuleProps) -> Maybe[str]:
    """Subset a granule to a GeoParquet file and return the output path.

    Download the specified granule (`props.granule`) obtained from a CMR search
    to the specified directory (`props.output_dir`), subset it to a GeoParquet
    file where it overlaps with the specified AOI (`props.aoi_gdf`), remove the
    downloaded granule file, and return the path to the output file.

    Return `Nothing` if the subset is empty (in which case no GeoParquet file
    was written), otherwise `Some[str]` indicating the output path of the
    GeoParquet file.
    """

    io_result = download_granule(props.maap, str(props.output_dir), props.granule)
    inpath = unsafe_perform_io(io_result.alt(raise_exception).unwrap())

    logger.debug(f"Subsetting {inpath}")
    gdf: gpd.GeoDataFrame = flow(
        subset_hdf5(inpath, props.aoi_gdf, props.columns, props.query),
        df_assign("filename", inpath),
    )
    osx.remove(inpath)

    if gdf.empty:
        logger.debug(f"Empty subset produced from {inpath}; not writing")
        return Nothing

    outpath = chext(".gpq", inpath)
    logger.debug(f"Writing subset to {outpath}")
    gdf_to_parquet(outpath, gdf).alt(raise_exception)

    return Some(outpath)


def init_process(logging_level: int) -> None:
    set_logging_level(logging_level)


def set_logging_level(logging_level: int) -> None:
    global logger
    logger.setLevel(logging_level)


def subset_granules(
    maap: MAAP,
    aoi_gdf: gpd.GeoDataFrame,
    columns: Sequence[str],
    query: str,
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
        return unsafe_perform_io(map_(is_successful)(path).unwrap())

    def append_subset(src: str) -> IOResultE[str]:
        to_file_props = dict(index=False, mode="a", driver="GPKG")
        logger.debug(f"Appending {src} to {dest}")

        return flow(
            gdf_read_parquet(src),
            bind_ioresult(partial(gdf_to_file, dest, to_file_props)),
            tap(pipe(always(src), osx.remove)),
            map_(always(src)),
        )

    # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.pool.Pool.imap
    chunksize = 10
    processes = os.cpu_count()
    payloads = (
        SubsetGranuleProps(granule, maap, aoi_gdf, columns, query, output_dir)
        for granule in granules
    )

    logger.info(f"Subsetting on {processes} processes (chunksize={chunksize})")

    with multiprocessing.Pool(processes, init_process, init_args) as pool:
        return flow(
            pool.imap_unordered(subset_granule, payloads, chunksize),
            map(lash(raise_exception)),  # Fail fast (if subsetting errored out)
            filter(subset_saved),  # Skip granules that produced empty subsets
            map(bind(bind(append_subset))),  # Append non-empty subset
            partial(Fold.collect, acc=IOSuccess(())),
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
        "10.3334/ORNLDAAC/2056",  # GEDI L4A DOI, v2.1
        help="Digital Object Identifier of collection to subset (https://www.doi.org/)",
    ),
    cmr_host: CMRHost = typer.Option(
        CMRHost.maap,
        help="CMR hostname",
    ),
    columns: str = typer.Option(
        ",".join(
            [
                "agbd",
                "agbd_se",
                "l2_quality_flag",
                "l4_quality_flag",
                "lat_lowestmode",
                "lon_lowestmode",
                "sensitivity",
                "sensitivity_a2",
            ]
        ),
        help="Comma-separated list of columns to select",
    ),
    query: str = typer.Option(
        "l2_quality_flag == 1"
        " and l4_quality_flag == 1"
        " and sensitivity > 0.95"
        " and sensitivity_a2 > 0.95",
        help="Boolean query expression to select rows",
    ),
    limit: int = typer.Option(
        10_000,
        help="Maximum number of granules to subset",
    ),
    output_dir: Path = typer.Option(
        f"{os.path.join(os.path.abspath(os.path.curdir), 'output')}",
        "-d",
        "--output-directory",
        help="Output directory for generated subset file",
        exists=False,
        file_okay=False,
        dir_okay=True,
        writable=True,
        readable=True,
        resolve_path=True,
    ),
    verbose: bool = typer.Option(False, help="Provide verbose output"),
) -> None:
    logging_level = logging.DEBUG if verbose else logging.INFO
    set_logging_level(logging_level)

    os.makedirs(output_dir, exist_ok=True)
    dest = output_dir / "gedi_subset.gpkg"

    # Remove existing combined subset file, primarily to support
    # testing.  When running in the context of a DPS job, there
    # should be no existing file since every job uses a unique
    # output directory.
    osx.remove(dest)

    maap = MAAP("api.ops.maap-project.org")

    IOResult.do(
        subsets
        for aoi_gdf in impure_safe(gpd.read_file)(aoi)
        for collection in find_collection(maap, cmr_host, {"doi": doi})
        for granules in impure_safe(maap.searchGranule)(
            cmr_host=cmr_host,
            collection_concept_id=collection["concept-id"],
            bounding_box=",".join(map(str)(aoi_gdf.total_bounds)),
            limit=limit,
        )
        for subsets in subset_granules(
            maap,
            aoi_gdf,
            [c.strip() for c in columns.split(",")],
            query,
            output_dir,
            dest,
            (logging_level,),
            filter(partial(granule_intersects, aoi_gdf.geometry[0]))(granules),
        )
    ).bind_ioresult(
        lambda subsets: IOSuccess(subsets)
        if subsets
        else IOFailure(ValueError(f"No granules intersect the AOI: {aoi}"))
    ).map(
        lambda subsets: logger.info(f"Subset {len(subsets)} granule(s) to {dest}")
    ).alt(
        raise_exception
    )


if __name__ == "__main__":
    typer.run(main)
