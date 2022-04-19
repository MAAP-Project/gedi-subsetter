import json
import logging
import os
import os.path
import warnings
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence, TypeVar, Union

import h5py
import numpy as np
import pandas as pd
import requests
from maap.Result import Granule
from returns.curry import curry, partial
from returns.functions import identity
from returns.io import IOFailure, IOResult, IOResultE, IOSuccess, impure_safe
from returns.iterables import Fold
from returns.pipeline import flow
from returns.pointfree import bimap, bind_ioresult, map_
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

from fp import K

# Suppress UserWarning: The Shapely GEOS version (3.10.2-CAPI-1.16.0) is incompatible
# with the GEOS version PyGEOS was compiled with (3.8.1-CAPI-1.13.3). Conversions
# between both will be slow.
#  shapely_geos_version, geos_capi_version_string
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import geopandas as gpd


_A = TypeVar("_A")
_B = TypeVar("_B")
_C = TypeVar("_C")
_D = TypeVar("_D")
_DF = TypeVar("_DF", bound=pd.DataFrame)
_T = TypeVar("_T")

logger = logging.getLogger(f"gedi_subset.{__name__}")


def pprint(value: Any) -> None:
    print(json.dumps(value, indent=2))


# str -> str -> str
def chext(ext: str, path: str) -> str:
    """Changes the extension of a path."""
    return f"{os.path.splitext(path)[0]}{ext}"


# (_T -> None) -> Iterable _T -> None
@curry
def for_each(f: Callable[[_T], None], xs: Iterable[_T]) -> None:
    """Applies a function to every element of an iterable."""
    for x in xs:
        f(x)


# (_A -> bool) -> (_A -> _B) -> _A -> _A | _B
@curry
def when(pred: Callable[[_A], bool], f: Callable[[_A], _B], a: _A) -> Union[_A, _B]:
    return f(a) if pred(a) else a


# (_B -> _C -> _D) -> (_A -> _B) -> (_A -> _C) -> (_A -> _D)
@curry
def converge(
    join: Callable[[_B], Callable[[_C], _D]],
    f: Callable[[_A], _B],
    g: Callable[[_A], _C],
) -> Callable[[_A], _D]:
    """Returns a unary function that joins the output of 2 other functions."""

    def do_join(x: _A) -> _D:
        return join(f(x))(g(x))

    return do_join


# str -> Any -> _DF -> _DF
@curry
def df_assign(col_name: str, val: Any, df: _DF) -> _DF:
    return df.assign(**{col_name: val})


@curry
def append_message(extra_message: str, e: Exception) -> Exception:
    message, *other_args = e.args if e.args else ("",)
    new_message = f"{message}: {extra_message}" if message else extra_message
    e.args = (new_message, *other_args)

    return e


def granule_downloader(
    dest_dir: str, *, overwrite=False
) -> Callable[[Granule], Optional[str]]:
    os.makedirs(dest_dir, exist_ok=True)

    def download_granule(granule: Granule) -> Optional[str]:
        return granule.getData(dest_dir, overwrite)

    return download_granule


@curry
def gdf_to_file(
    file: Union[str, os.PathLike], props: Mapping[str, Any], gdf: gpd.GeoDataFrame
) -> IOResultE[None]:
    # Unfortunately, using mode='a' when the target file does not exist throws an
    # exception rather than simply creating a new file.  Therefore, in that case, we
    # switch to mode='w' to avoid the error.
    mode = props.get("mode")
    props = dict(props, mode="w") if mode == "a" and not os.path.exists(file) else props

    logger.debug(
        f"Empty GeoDataFrame; not writing {file}"
        if gdf.empty
        else f"Writing to {file}"
    )

    return (
        IOSuccess(None)
        if gdf.empty
        else impure_safe(gdf.to_file)(file, **props).alt(
            lambda e: e
            if f"{file}" in f"{e}"
            else append_message(f"writing to {file}", e)
        )
    )


@curry
def append_gdf_file(
    dest: Union[str, os.PathLike],
    src: Union[str, os.PathLike],
) -> IOResultE[Union[str, os.PathLike]]:
    to_file_options = {"index": False, "mode": "a", "driver": "GPKG"}

    return flow(
        src,
        impure_safe(gpd.read_file),
        bind_ioresult(partial(gdf_to_file, dest, to_file_options)),
        map_(K(src)),
    )


@curry
def combine_gdf_files(
    dest: Union[str, os.PathLike], srcs: Iterable[Union[str, os.PathLike]]
) -> IOResultE[None]:
    return flow(
        srcs,
        partial(map, append_gdf_file(dest)),
        partial(map, IOResult.swap),
        partial(Fold.collect_all, acc=IOSuccess(())),
        bind_ioresult(
            lambda errors: (
                IOFailure(tuple(map(str, errors))) if len(errors) else IOSuccess(None)
            )
        ),
    )


def get_geo_boundary(iso: str, level: int) -> gpd.GeoDataFrame:
    file_path = f"/projects/my-public-bucket/iso3/{iso}-ADM{level}.json"

    if not os.path.exists(file_path):
        r = requests.get(
            "https://www.geoboundaries.org/gbRequest.html",
            dict(ISO=iso, ADM=f"ADM{level}"),
        )
        r.raise_for_status()
        dl_url = r.json()[0]["gjDownloadURL"]
        geo_boundary = requests.get(dl_url).json()

        with open(file_path, "w") as out:
            out.write(json.dumps(geo_boundary))

    return gpd.read_file(file_path)


def subset_gedi_granule(
    path: Union[str, os.PathLike],
    aoi: gpd.GeoDataFrame,
    filter_cols=["lat_lowestmode", "lon_lowestmode"],
) -> gpd.GeoDataFrame:
    """
    Subset a GEDI granule by a polygon in CRS 4326

    path = path to a granule h5 file that's already been downloaded
    aoi = a shapely polygon of the aoi

    return GeoDataFrame of granule subsetted to specified `aoi`
    """
    return subset_h5(path, aoi, filter_cols)


@curry
def granule_intersects(aoi: BaseGeometry, granule: Granule):
    """Determines whether or not a granule intersects an Area of Interest

    Returns `True` if the polygon determined by the points in the `granule`'s
    horizontal spatial domain intersects the geometry of the Area of Interest;
    `False` otherwise.
    """
    points = granule["Granule"]["Spatial"]["HorizontalSpatialDomain"]["Geometry"][
        "GPolygon"
    ]["Boundary"]["Point"]
    polygon = Polygon(
        [[float(p["PointLongitude"]), float(p["PointLatitude"])] for p in points]
    )

    return polygon.intersects(aoi)


def spatial_filter(beam, aoi):
    """
    Find the record indices within the aoi
    TODO: Make this faster
    """
    lat = beam["lat_lowestmode"][:]
    lon = beam["lon_lowestmode"][:]
    i = np.arange(0, len(lat), 1)  # index
    geo_arr = list(zip(lat, lon, i))
    l4adf = pd.DataFrame(geo_arr, columns=["lat_lowestmode", "lon_lowestmode", "i"])
    l4agdf = gpd.GeoDataFrame(
        l4adf, geometry=gpd.points_from_xy(l4adf.lon_lowestmode, l4adf.lat_lowestmode)
    )
    l4agdf.crs = "EPSG:4326"
    # TODO: is it faster with a spatial index, or rough pass with BBOX first?
    bbox = aoi.geometry[0].bounds
    l4agdf_clip = l4agdf.cx[bbox[0] : bbox[2], bbox[1] : bbox[3]]
    l4agdf_gsrm = l4agdf_clip[l4agdf_clip["geometry"].within(aoi.geometry[0])]
    indices = l4agdf_gsrm.i

    return indices


@curry
def subset_h5(
    path: Union[str, os.PathLike], aoi: gpd.GeoDataFrame, filter_cols: Sequence[str]
) -> gpd.GeoDataFrame:
    """
    Extract the beam data only for the aoi and only columns of interest
    """
    subset_df = pd.DataFrame()

    with h5py.File(path, "r") as hf_in:
        # loop through BEAMXXXX groups
        for v in list(hf_in.keys()):
            if v.startswith("BEAM"):
                col_names = []
                col_val = []
                beam = hf_in[v]

                indices = spatial_filter(beam, aoi)

                # TODO: when to spatial subset?
                for key, value in beam.items():
                    # looping through subgroups
                    if isinstance(value, h5py.Group):
                        for key2, value2 in value.items():
                            if key2 not in filter_cols:
                                continue
                            if key2 != "shot_number":
                                # xvar variables have 2D
                                if key2.startswith("xvar"):
                                    for r in range(4):
                                        col_names.append(key2 + "_" + str(r + 1))
                                        col_val.append(value2[:, r][indices].tolist())
                                else:
                                    col_names.append(key2)
                                    col_val.append(value2[:][indices].tolist())

                    # looping through base group
                    else:
                        if key not in filter_cols:
                            continue
                        # xvar variables have 2D
                        if key.startswith("xvar"):
                            for r in range(4):
                                col_names.append(key + "_" + str(r + 1))
                                col_val.append(value[:, r][indices].tolist())

                        else:
                            col_names.append(key)
                            col_val.append(value[:][indices].tolist())

                # create a pandas dataframe
                beam_df = pd.DataFrame(map(list, zip(*col_val)), columns=col_names)
                # Inserting BEAM names
                beam_df.insert(
                    0, "BEAM", np.repeat(str(v), len(beam_df.index)).tolist()
                )
                # Appending to the subset_df dataframe
                subset_df = pd.concat([subset_df, beam_df])

    # all_gdf = gpd.GeoDataFrame(subset_df, geometry=gpd.points_from_xy(subset_df.lon_lowestmode, subset_df.lat_lowestmode))
    all_gdf = gpd.GeoDataFrame(
        subset_df.loc[:, ~subset_df.columns.isin(["lon_lowestmode", "lat_lowestmode"])],
        geometry=gpd.points_from_xy(subset_df.lon_lowestmode, subset_df.lat_lowestmode),
    )
    all_gdf.crs = "EPSG:4326"
    # TODO: Drop the lon and lat columns after geometry creation(or during)
    # TODO: document how many points before and after filtering
    # print(f"All points {all_gdf.shape}")
    # subset_gdf = all_gdf[all_gdf['geometry'].within(aoi.geometry[0])]
    subset_gdf = all_gdf  # Doing the spatial search first didn't help at all, so maybe the spatial query is the slow part.
    # print(f"Subset points {subset_gdf.shape}")

    return subset_gdf


def write_subset(infile, gdf):
    """
    Write GeoDataFrame to Flatgeobuf
    TODO: What's the most efficient format?
    """
    outfile = infile.replace(".h5", ".fgb")
    gdf.to_file(outfile, driver="FlatGeobuf")

    return outfile
