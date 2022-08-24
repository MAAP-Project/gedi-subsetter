import json
import logging
import os
import os.path
import warnings
from typing import Any, Callable, List, Mapping, Sequence, TypeVar, Union

import h5py
import numpy as np
import pandas as pd
import requests
from maap.Result import Granule
from returns.curry import curry
from returns.io import IOResultE, impure_safe
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry

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
    message, *other_args = e.args if e.args else ("",)  # pytype: disable=bad-unpacking
    new_message = f"{message}: {extra_message}" if message else extra_message
    e.args = (new_message, *other_args)

    return e


@curry
def gdf_to_file(
    file: Union[str, os.PathLike], props: Mapping[str, Any], gdf: gpd.GeoDataFrame
) -> IOResultE[None]:
    # Unfortunately, using mode='a' when the target file does not exist throws an
    # exception rather than simply creating a new file.  Therefore, in that case, we
    # switch to mode='w' to avoid the error.
    mode = props.get("mode")
    props = dict(props, mode="w") if mode == "a" and not os.path.exists(file) else props

    return impure_safe(gdf.to_file)(file, **props)


@curry
def gdf_to_parquet(
    path: Union[str, os.PathLike], gdf: gpd.GeoDataFrame
) -> IOResultE[None]:
    """Write a GeoDataFrame to the Parquet format."""
    return impure_safe(gdf.to_parquet)(path)


def gdf_read_parquet(path: Union[str, os.PathLike[str]]) -> IOResultE[gpd.GeoDataFrame]:
    """Read a Parquet object from a file path and return it as a GeoDataFrame."""
    return impure_safe(gpd.read_parquet)(path)


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
    path: Union[str, os.PathLike],
    aoi: gpd.GeoDataFrame,
    filter_cols: Sequence[str],
    expr: str,
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
                beam_df = pd.DataFrame(
                    map(list, zip(*col_val)), columns=col_names
                ).query(expr)
                # Inserting BEAM names
                beam_df.insert(0, "BEAM", np.repeat(v[5:], len(beam_df.index)).tolist())
                # Appending to the subset_df dataframe
                subset_df = pd.concat([subset_df, beam_df])

    all_gdf = gpd.GeoDataFrame(
        subset_df.loc[:, ~subset_df.columns.isin(["lon_lowestmode", "lat_lowestmode"])],
        geometry=gpd.points_from_xy(subset_df.lon_lowestmode, subset_df.lat_lowestmode),
    )
    all_gdf.crs = "EPSG:4326"
    # TODO: Drop the lon and lat columns after geometry creation(or during)
    # TODO: document how many points before and after filtering
    # print(f"All points {all_gdf.shape}")
    # subset_gdf = all_gdf[all_gdf['geometry'].within(aoi.geometry[0])]
    # Doing the spatial search first didn't help at all, so maybe the spatial query is
    # the slow part.
    subset_gdf = all_gdf
    # print(f"Subset points {subset_gdf.shape}")

    return subset_gdf


def subset_hdf5(
    path: str,
    aoi: gpd.GeoDataFrame,
    columns: Sequence[str],
    expr: str,
) -> gpd.GeoDataFrame:
    def subset_beam(beam: h5py.Group) -> gpd.GeoDataFrame:
        def append_series(path: str, value: Union[h5py.Group, h5py.Dataset]) -> None:
            if (name := path.split("/")[-1]) in columns:
                series.append(pd.Series(value, name=name))

        series: List[pd.Series] = []
        beam.visititems(append_series)
        df = pd.concat(series, axis=1).query(expr)
        df.insert(0, "BEAM", beam.name[5:])

        x, y = df.lon_lowestmode, df.lat_lowestmode
        df.drop(["lon_lowestmode", "lat_lowestmode"], axis=1, inplace=True)
        gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(x, y), crs="EPSG:4326")

        return gdf[gdf.geometry.within(aoi.geometry[0])]

    with h5py.File(path) as hdf5:
        beams = (value for key, value in hdf5.items() if key.startswith("BEAM"))
        beam_dfs = (subset_beam(beam) for beam in beams)
        beams_df = pd.concat(beam_dfs, ignore_index=True, copy=False)

    return beams_df


def write_subset(infile, gdf):
    """
    Write GeoDataFrame to Flatgeobuf
    TODO: What's the most efficient format?
    """
    outfile = infile.replace(".h5", ".fgb")
    gdf.to_file(outfile, driver="FlatGeobuf")

    return outfile
