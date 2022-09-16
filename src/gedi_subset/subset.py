#!/usr/bin/env -S python -W ignore::FutureWarning -W ignore::UserWarning

import json
import logging
import multiprocessing
import os
import os.path
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, Tuple

import geopandas as gpd
import h5py
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

from gedi_subset import osx
from gedi_subset.fp import always, filter, map
from gedi_subset.gedi_utils import (
    chext,
    gdf_read_parquet,
    gdf_to_file,
    gdf_to_parquet,
    granule_intersects,
    subset_hdf5,
)
from gedi_subset.maapx import download_granule, find_collection


class CMRHost(str, Enum):
    maap = "cmr.maap-project.org"
    nasa = "cmr.earthdata.nasa.gov"


with open(os.path.join(os.path.dirname(__file__), "doi_cfg.json")) as config_file:
    config = json.load(config_file)

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

    with h5py.File(inpath) as hdf5:
        gdf = subset_hdf5(hdf5, props.aoi_gdf, props.columns, props.query)

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


def config_defaults(
    config: Mapping[str, Any], doi: str, columns: str, query: str
) -> Tuple[str, str, str]:
    doi_cfg = config.get(doi, None)

    if doi_cfg:
        doi = doi_cfg["doi"]
        if not columns:
            columns = ",".join(doi_cfg["columns"])

        if not query:
            query = "".join(doi_cfg["query"])
    else:
        if not all([columns, query]):
            raise ValueError(
                f"""No default values found for: '{doi}'
                --columns and --query are required"""
            )

    logging.debug(f"doi: {doi}")
    logging.debug(f"columns: {columns}")
    logging.debug(f"query: {query}")

    return doi, columns, query


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
        help=(
            "Digital Object Identifier (DOI) of collection to subset"
            " (https://www.doi.org/)"
            " Can be a specific DOI"
            f" or one of these logical names: {', '.join(config.keys())}"
        ),
    ),
    cmr_host: CMRHost = typer.Option(
        CMRHost.maap,
        help="CMR hostname",
    ),
    columns: str = typer.Option(
        None,
        help="Comma-separated list of columns to select",
    ),
    query: str = typer.Option(
        None,
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

    doi, columns, query = config_defaults(config, doi, columns, query)

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
