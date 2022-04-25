#!/usr/bin/env -S python -W ignore::FutureWarning

import logging
import multiprocessing
import os
import os.path
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Tuple

import geopandas as gpd
import osx
import typer
from fp import K, filter, map
from gedi_utils import (
    append_gdf_file,
    chext,
    df_assign,
    gdf_to_file,
    granule_intersects,
    subset_h5,
)
from maap.maap import MAAP
from maap.Result import Granule
from maapx import download_granule, find_collection
from returns.curry import partial
from returns.functions import raise_exception, tap
from returns.io import IO, IOResultE, IOSuccess, impure_safe
from returns.iterables import Fold
from returns.maybe import Maybe, Nothing, Some
from returns.methods import unwrap_or_failure
from returns.pipeline import flow, is_successful, pipe
from returns.pointfree import bind_ioresult, cond, lash, map_
from returns.result import Failure, Success
from returns.unsafe import unsafe_perform_io


class CMRHost(str, Enum):
    maap = "cmr.maap-project.org"
    nasa = "cmr.earthdata.nasa.gov"


LOGGING_FORMAT = "%(asctime)s [%(processName)s:%(name)s] [%(levelname)s] %(message)s"

logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
logger = logging.getLogger("gedi_subset")


@dataclass
class ProcessGranuleProps:
    granule: Granule
    maap: MAAP
    aoi_gdf: gpd.GeoDataFrame
    output_directory: Path


def cpu_count() -> int:
    if sys.platform == "darwin":
        return os.cpu_count() or 1
    if sys.platform == "linux":
        return len(os.sched_getaffinity(0))
    return 1


@impure_safe
def process_granule(props: ProcessGranuleProps) -> IOResultE[Maybe[str]]:
    filter_cols = [
        "agbd",
        "agbd_se",
        "l4_quality_flag",
        "sensitivity",
        "lat_lowestmode",
        "lon_lowestmode",
    ]
    outdir = str(props.output_directory)
    io_result = download_granule(props.maap, outdir, props.granule)
    inpath = unsafe_perform_io(io_result.alt(raise_exception).unwrap())
    outpath = chext(".fgb", inpath)

    logger.debug(f"Subsetting {inpath} to {outpath}")

    flow(
        subset_h5(inpath, props.aoi_gdf, filter_cols),
        df_assign("filename", inpath),
        gdf_to_file(outpath, dict(index=False, driver="FlatGeobuf")),
        bind_ioresult(lambda _: osx.remove(inpath)),
        lash(raise_exception),
    )

    return osx.exists(outpath).bind(cond(Maybe, outpath))


def init_process(logging_level: int) -> None:
    set_logging_level(logging_level)


def set_logging_level(logging_level: int) -> None:
    global logger
    logger.setLevel(logging_level)


def subset_granules(
    maap: MAAP,
    aoi_gdf: gpd.GeoDataFrame,
    output_directory: Path,
    dest: Path,
    init_args: Tuple[Any, ...],
    granules: Iterable[Granule],
) -> IOResultE[Tuple[str, ...]]:
    # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.pool.Pool.imap
    chunksize = 10
    processes = os.cpu_count()

    logger.info(f"Subsetting on {processes} processes (chunksize={chunksize})")

    props = (
        ProcessGranuleProps(granule, maap, aoi_gdf, output_directory)
        for granule in granules
    )

    with multiprocessing.Pool(processes, init_process, init_args) as pool:
        return flow(
            pool.imap_unordered(process_granule, props, chunksize),
            filter(lambda r: map_(is_successful)(r) == IOSuccess(True)),
            map(map_(unwrap_or_failure)),
            map(tap(map_(pipe(f"Appending {{}} to {dest}".format, logger.debug)))),
            map(bind_ioresult(partial(append_gdf_file, dest))),
            map(bind_ioresult(lambda src: osx.remove(src).map(K(src)))),
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
        # "10.3334/ORNLDAAC/1986",  # GEDI L4A DOI, v2
        "10.3334/ORNLDAAC/2056",  # GEDI L4A DOI, v2.1
        help="Digital Object Identifier of collection to subset (https://www.doi.org/)",
    ),
    cmr_host: CMRHost = typer.Option(
        CMRHost.maap,
        help="CMR hostname",
    ),
    limit: int = typer.Option(
        10_000,
        help="Maximum number of granules to subset",
    ),
    output_directory: Path = typer.Option(
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

    os.makedirs(output_directory, exist_ok=True)
    dest = output_directory / "gedi_subset.gpkg"

    # Remove existing combined subset file, primarily to support
    # testing.  When running in the context of a DPS job, there
    # should be no existing file since every job uses a unique
    # output directory.
    osx.remove(dest)

    maap = MAAP("api.ops.maap-project.org")

    result = IO.do(
        Success(subsets)
        if subsets
        else Failure(ValueError("No granules intersect AOI"))
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
            output_directory,
            dest,
            (logging_level,),
            filter(partial(granule_intersects, aoi_gdf.geometry[0]))(granules),
        )
    )

    flow(
        unsafe_perform_io(result),
        map_(pipe(len, f"Subset {{}} granule(s) to {dest}".format, logger.info)),
        lash(raise_exception),
    )


if __name__ == "__main__":
    typer.run(main)
