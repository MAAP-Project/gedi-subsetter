import json
import logging
import os
import os.path
import warnings
from itertools import chain
from typing import Any, Callable, Iterable, Mapping, TypeVar, Union

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


@curry
def append_message(extra_message: str, e: Exception) -> Exception:
    message, *other_args = e.args if e.args else ("",)
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


def subset_hdf5(
    hdf5: h5py.File,
    aoi: gpd.GeoDataFrame,
    columns: Iterable[str],
    query: str,
) -> gpd.GeoDataFrame:
    """Subset the data in an HDF5 file into a ``geopandas.GeoDataFrame``.

    The data within the HDF5 file is "subsetted" by selecting only data for points that
    fall within the specified area of interest (AOI) and also satisfy the specified
    query criteria.  The resulting ``geopandas.GeoDataFrame`` is further reduced to
    including only the specified columns, which must be names of datasets within the
    HDF5 file (and more specifically, only to groups named with the prefix `"BEAM"`).

    To illustrate, assume an HDF5 file (`hdf5`) structured like so (values are for
    illustration purposes only):

    ```
    GEDI04_A_2019146134206_O02558_01_T05641_02_002_02_V002.h5
    +-- ANCILLARY
        +-- ...
    +-- BEAM0000
        +-- agbd: 1.271942, 1.3311168, 1.1160929
        +-- sensitivity: 0.9, 0.97, 0.99
        +-- l2_quality_flag: 0, 1, 1
        +-- lat_lowestmode: -1.82556, -4.82514, -1.82471
        +-- lon_lowestmode: 12.06648, 12.06678, 12.06707
    +-- BEAM0001
        +-- agbd: 1.1715966, 1.630395, 3.5265787
        +-- sensitivity: 0.93, 0.96, 0.98
        +-- l2_quality_flag: 0, 1, 1
        +-- lat_lowestmode: -1.82557, -4.82515, -1.82472
        +-- lon_lowestmode: 12.06649, 12.06679, 12.06708
    +-- METADATA
        +-- ...
    ```

    Further, assume an AOI (`aoi`) with the following lon-lat coordinates in
    counter-clockwise order (a polygon): (8.45, 2.35), (14.35, 2.35), (14.35, -4.15),
    (8.45, -4.15), (8.45, 2.35).

    Subsetting the `hdf5` file to points within the `aoi`, matching the criteria
    `sensitivity > 0.95 and l2_quality_flag == 1`, and selecting only the `columns`
    (datasets) named `"agbd"` and `"sensitivity"`, would result in the following data:

    ```
    filename    BEAM  agbd      sensitivity              geometry
    GEDI04_...     0  1.116093         0.99  (12.06707, -1.82471)
    GEDI04_...     1  3.526579         0.98  (12.06708, -1.82472)
    ```

    Assumptions:

    - The HDF5 file contains groups that are named with the prefix `"BEAM"`, and the
      suffix is parseable as an integer.
    - Every `"BEAM*"` group contains datasets named `lat_lowestmode` and
      `lon_lowestmode`, representing the latitude and longitude, respectively, which are
      used for the geometry of the resulting ``GeoDataFrame``.
    - For every column name in `columns` and every column name appearing in the `query`
      expression, every `"BEAM*"` group contains a dataset of the same name.

    Further, for traceability, the `filename` and `BEAM` columns are inserted,
    regardless of the specified `columns` value.

    See the code example below for the code that corresponds to this illustration.

    Parameters
    ----------
    hdf5 : h5py.File
        HDF5 file to subset.
    aoi : gpd.GeoDataFrame
        Area of Interest.  The subset is limited to data points that fall within this
        area of interest, as determined by the `lat_lowestmode` and `lon_lowestmode`
        datasets of each `"BEAM*"` group within the HDF5 file.
    columns : Iterable[str]
        Column names to be included in the subset.  The specified column names must
        match dataset names within the `"BEAM*"` groups of the HDF5 file.
        Although the `query` expression may include column names not given in this
        iterable of names, the resulting ``GeoDataFrame`` will contain only the columns
        specified by this parameter, along with `filename` (str) and `BEAM` (int)
        columns (for traceability).
    query : str
        Query expression for subsetting the rows of the data.  After "flattening" all
        of the `"BEAM*"` groups of the HDF5 file into rows across with columns formed by
        the groups' datasets, only rows satisfying this query expression are returned.

    Returns
    -------
    subset : gpd.GeoDataFrame
        GeoDataFrame containing the subset of the data from the HDF5 file that fall
        within the specified area of interest and satisfy the specified query.  Columns
        are limited to the specified iterable of column names, along with `filename`
        (str) and `BEAM` (int) columns.

    Examples
    --------
    The following HDF5 file corresponds to the data illustrated above.  In this example,
    we're simply generating it on-the-fly in memory, rather than reading from disk, as
    would be the norm:

    >>> import io
    >>> bio = io.BytesIO()
    >>> with h5py.File(bio, "w") as hdf5:  # doctest: +ELLIPSIS
    ...     group = hdf5.create_group("BEAM0000")
    ...     group.create_dataset("agbd", data=[1.271942, 1.3311168, 1.1160929])
    ...     group.create_dataset("l2_quality_flag", data=[0, 1, 1], dtype="i1")
    ...     group.create_dataset("lat_lowestmode", data=[-1.82556, -9.82514, -1.82471])
    ...     group.create_dataset("lon_lowestmode", data=[12.06648, 12.06678, 12.06707])
    ...     group.create_dataset("sensitivity", data=[0.9, 0.97, 0.99])
    ...     group = hdf5.create_group("BEAM0001")
    ...     group.create_dataset("agbd", data=[1.1715966, 1.630395, 3.5265787])
    ...     group.create_dataset("l2_quality_flag", data=[0, 1, 1], dtype="i1")
    ...     group.create_dataset("lat_lowestmode", data=[-1.82557, -9.82515, -1.82472])
    ...     group.create_dataset("lon_lowestmode", data=[12.06649, 12.06679, 12.06708])
    ...     group.create_dataset("sensitivity", data=[0.93, 0.96, 0.98])
    <HDF5 dataset "agbd": ...>
    <HDF5 dataset "l2_quality_flag": ...>
    <HDF5 dataset "lat_lowestmode": ...>
    <HDF5 dataset "lon_lowestmode": ...>
    <HDF5 dataset "sensitivity": ...>
    <HDF5 dataset "agbd": ...>
    <HDF5 dataset "l2_quality_flag": ...>
    <HDF5 dataset "lat_lowestmode": ...>
    <HDF5 dataset "lon_lowestmode": ...>
    <HDF5 dataset "sensitivity": ...>

    To make it easier to see what subsetting the HDF5 file will do, let's take a look at
    what the HDF5 data looks like "flattened" into a ``geopandas.GeoDataFrame``, where
    the `"BEAM*"` groups are concatenated, and their datasets appear as columns:

    >>> with h5py.File(bio) as hdf5:
    ...     pd.concat(
    ...         (gpd.GeoDataFrame({
    ...             name: pd.Series(data, name=name)
    ...             for name, data in group.items()
    ...         })
    ...         for group in hdf5.values()),
    ...         ignore_index=True,
    ...     )
           agbd  l2_quality_flag  lat_lowestmode  lon_lowestmode  sensitivity
    0  1.271942                0        -1.82556        12.06648         0.90
    1  1.331117                1        -9.82514        12.06678         0.97
    2  1.116093                1        -1.82471        12.06707         0.99
    3  1.171597                0        -1.82557        12.06649         0.93
    4  1.630395                1        -9.82515        12.06679         0.96
    5  3.526579                1        -1.82472        12.06708         0.98

    Next, we'll obtain an area of interest as a ``geopandas.GeoDataFrame``.  Here, we're
    constructing it from a features list, but typically, it might be obtained via
    ``geopandas.read_file``:

    >>> aoi = gpd.GeoDataFrame.from_features([{"properties": {}, "geometry": {
    ...    "type": "Polygon",
    ...    "coordinates": [
    ...        [
    ...            [ 8.45,  2.35],
    ...            [14.35,  2.35],
    ...            [14.35, -4.15],
    ...            [ 8.45, -4.15],
    ...            [ 8.45,  2.35],
    ...        ]
    ...    ],
    ... }}])

    We can now subset the data in the HDF5 file to points that fall within the AOI,
    selecting only the desired columns (i.e., named datasets within the HDF5 file), and
    selecting only the rows that satisfy the specified query:

    >>> with h5py.File(bio) as hdf5:  # doctest: +ELLIPSIS
    ...     gdf = subset_hdf5(
    ...         hdf5, aoi, ["sensitivity", "agbd"],
    ...         "l2_quality_flag == 1 and sensitivity > 0.95"
    ...     )
    ...     # Since the source of our HDF5 file is an ``io.BytesIO``, we'll drop the
    ...     # `filename` column (which refers to the memory location of the
    ...     # ``io.BytesIO``, not a filename).
    ...     gdf.drop(columns=["filename"])
       BEAM      agbd  sensitivity                   geometry
    0     0  1.116093         0.99  POINT (12.06707 -1.82471)
    1     1  3.526579         0.98  POINT (12.06708 -1.82472)

    Note that the resulting ``geopandas.GeoDataFrame`` contains only the specified
    columns (`agbd` and `sensitivity`), and only the rows (only 1 from each "beam" in
    this example) that have a geometry that falls within the AOI and also satisfy the
    query (i.e., `l2_quality_flag == 1` and `sensitivity > 0.95`).

    Note also that although the `l2_quality_flag` was specified in the query, it does
    not appear in the result because it was not specified in the iterable of column
    names.  This means that the query is not limited to refering to only names given in
    the iterable of column names, but may refer to any of the dataset names within the
    `"BEAM*"` groups.
    """

    def datasets(group: h5py.Group) -> Iterable[h5py.Dataset]:
        """Return an iterable of all 1-dimensional ``h5py.Dataset``s from all levels
        within an ``h5py.Group``.
        """
        return chain.from_iterable(
            datasets(value)
            if isinstance(value, h5py.Group)
            else [(name, value)]
            if value.ndim == 1
            else []
            for name, value in group.items()
        )

    def subset_beam(beam: h5py.Group) -> gpd.GeoDataFrame:
        """Subset an individual `"BEAM*"` group as described above."""
        df_columns = (pd.Series(data, name=name) for name, data in datasets(beam))
        df = pd.concat(df_columns, axis=1)
        # Keep only the rows matching the specified query
        df.query(query, inplace=True)
        # Grab the coordinates for the geometry, before dropping columns
        x, y = df.lon_lowestmode, df.lat_lowestmode
        # Drop all columns NOT specified by the columns parameter
        df.drop(columns=list(set(df.columns) - set(columns)), inplace=True)
        # Insert "BEAM" number column by converting numerical suffix to an int
        df.insert(0, "BEAM", int(beam.name[5:]))
        gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(x, y), crs="EPSG:4326")

        # Select only the data that falls within the area of interest
        return gdf[gdf.geometry.within(aoi.geometry[0])]

    beams = (group for name, group in hdf5.items() if name.startswith("BEAM"))
    beams_gdf = pd.concat(map(subset_beam, beams), ignore_index=True, copy=False)
    beams_gdf.insert(0, "filename", os.path.basename(hdf5.filename))

    return beams_gdf


def write_subset(infile, gdf):
    """
    Write GeoDataFrame to Flatgeobuf
    TODO: What's the most efficient format?
    """
    outfile = infile.replace(".h5", ".fgb")
    gdf.to_file(outfile, driver="FlatGeobuf")

    return outfile
