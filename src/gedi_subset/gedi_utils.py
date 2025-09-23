import json
import logging
import os
import os.path
import warnings
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any, cast

import h5py
import pandas as pd
import requests
import shapely
from maap.Result import Granule
from shapely.geometry.base import BaseGeometry

from gedi_subset.h5frame import h5py_pandas_projector

# Suppress UserWarning: The Shapely GEOS version (3.10.2-CAPI-1.16.0) is incompatible
# with the GEOS version PyGEOS was compiled with (3.8.1-CAPI-1.13.3). Conversions
# between both will be slow.
#  shapely_geos_version, geos_capi_version_string
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import geopandas as gpd


logger = logging.getLogger(f"gedi_subset.{__name__}")


def pprint(value: Any) -> None:
    print(json.dumps(value, indent=2))


def chext(ext: str, path: str) -> str:
    """Changes the extension of a path."""
    return f"{os.path.splitext(path)[0]}{ext}"


def concat_parquet_files(files: Iterable[Path], dest: Path) -> Path:
    import pyarrow.parquet as pq

    if dest.suffix.lower() not in {".fgb", ".gpkg", ".parquet"}:
        msg = f"Unsupported format.  Expected '.fgb', '.gpkg', or '.parquet': {dest}"
        raise ValueError(msg)

    sources = tuple(files)
    schema = pq.ParquetFile(sources[0]).schema_arrow
    temp_dest = dest.with_suffix(".parquet")

    # Combine all parquet files into a single parquet file.
    with pq.ParquetWriter(temp_dest, schema=schema) as writer:
        for file in files:
            writer.write_table(pq.read_table(file, schema=schema))

    # If the destination file must be a different format, then reformat it and
    # remove the temporary combined parquet file.
    if temp_dest != dest:
        gdf: gpd.GeoDataFrame = gpd.read_parquet(temp_dest)
        gdf.to_file(dest)
        os.remove(temp_dest)

    return dest


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


def granule_geometry(granule: Granule) -> BaseGeometry:
    gpolygon = (
        granule.get("Granule", {})
        .get("Spatial", {})
        .get("HorizontalSpatialDomain", {})
        .get("Geometry", {})
        .get("GPolygon", [])
    )
    gpolygons = gpolygon if isinstance(gpolygon, list) else [gpolygon]
    boundaries = [gpolygon.get("Boundary", {}) for gpolygon in gpolygons]
    polygons = [
        shapely.Polygon(
            (
                (point["PointLongitude"], point["PointLatitude"])
                for boundary in boundaries
                for point in boundary.get("Point", [])
            )
            # TODO: The second argument (`holes`) to the Polygon constructor
            # should be constructed from the ECHO-10 XML ExclusiveZones element.
            # See https://git.earthdata.nasa.gov/projects/EMFD/repos/echo-schemas/browse/schemas/10.0/MetadataCommon.xsd#125  # noqa: E501
        )
    ]

    return shapely.union_all(polygons)


def granule_intersects(aoi: shapely.Geometry, granule: Granule):
    """Determines whether or not a granule intersects an Area of Interest

    Returns `True` if the polygon determined by the points in the `granule`'s
    horizontal spatial domain intersects the geometry of the Area of Interest;
    `False` otherwise.
    """
    return granule_geometry(granule).intersects(aoi)


def is_coverage_beam(beam: h5py.Group) -> bool:
    return "COVERAGE" in beam.attrs.get("description", "").upper()


def is_power_beam(beam: h5py.Group) -> bool:
    return "POWER" in beam.attrs.get("description", "").upper()


def beam_filter_from_names(names: Sequence[str]):
    def is_named_beam(beam: h5py.Group) -> bool:
        return isinstance(beam.name, str) and any(
            name.upper() in beam.name.upper() for name in names
        )

    return is_named_beam


def subset_hdf5(
    hdf5: h5py.Group,
    *,
    aoi: gpd.GeoDataFrame,
    lat_col: str,
    lon_col: str,
    beam_filter: Callable[[h5py.Group], bool] = lambda _: True,
    columns: Sequence[str],
    query: str | None = None,
) -> gpd.GeoDataFrame:
    """Subset the data in an HDF5 Group into a ``geopandas.GeoDataFrame``.

    The data within the HDF5 group is "subsetted" by selecting data only for points,
    determined by the `lat_lowestmode` and `lon_lowestmode` datasets within the group,
    that fall within the specified area of interest (AOI) and also satisfy the specified
    query criteria.  The resulting ``geopandas.GeoDataFrame`` is further reduced to
    include only the specified columns, which must be names of datasets within the
    HDF5 group (specifically, datasets within subgroups named with the prefix `"BEAM"`
    for which invocation of the specified ``beam_filter`` callable returns ``True``).

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
      filename  BEAM      agbd  sensitivity              geometry
    GEDI04_...  0000  1.116093         0.99  (12.06707, -1.82471)
    GEDI04_...  0001  3.526579         0.98  (12.06708, -1.82472)
    ```

    Assumptions:

    - The HDF5 group/file contains subgroups that are named with the prefix `"BEAM"`.
    - Every `"BEAM*"` subgroup contains degree unit datasets with names given by
      the specified ``lat_col`` and ``lon_col`` parameters, representing the
      latitude and longitude, respectively, used to create the ``geometry``
      column of the resulting ``GeoDataFrame``.
    - For every column name in `columns` and every column name appearing in the `query`
      expression, every `"BEAM*"` subgroup contains a dataset of the same name.

    Further, for traceability, the `filename` column is inserted, regardless of
    the specified `columns` value.

    See the code example below for the code that corresponds to this illustration.

    Parameters
    ----------
    hdf5
        HDF5 group to subset (typically an ``h5py.File`` instance).
    aoi
        Area of Interest.  The subset is limited to data points that fall within this
        area of interest, as determined by the latitude and longitude datasets of each
        `"BEAM*"` group within the HDF5 file.
    lat_col
        Name of the latitude dataset used for the resulting ``GeoDataFrame`` geometry.
    lon_col
        Name of the longitude dataset used for the resulting ``GeoDataFrame`` geometry.
    beam_filter
        Callable used to determine whether or not a top-level BEAM subgroup within the
        specified ``hdf5`` group should be included in the subset. This callable is
        called once for each subgroup that has a name prefixed with `"BEAM"`. If not
        supplied, the default callable always returns ``True``, such that every
        ``"BEAM*"`` subgroup is included. For convenience, the predicate functions
        py:`is_coverage_beam` and py:`is_power_beam` may be used. Further, the function
        returned by calling py:`beam_filter_from_names` with a specific list of BEAM
        names may be used.
    columns
        Column names to be included in the subset.  The specified column names must
        match dataset names within the `"BEAM*"` groups of the HDF5 file.  Although the
        `query` expression may include column names not given in this sequence of names,
        the resulting ``GeoDataFrame`` will contain only the columns specified by this
        parameter, along with `filename` (str) and `BEAM` (str) columns (for
        traceability).
    query
        Query expression for subsetting the rows of the data.  After "flattening" all
        of the `"BEAM*"` groups of the HDF5 file into rows across with columns formed by
        the groups' datasets, only rows satisfying this query expression are returned.
        If not specified, _all_ rows are returned.

    Returns
    -------
    subset : gpd.GeoDataFrame
        GeoDataFrame containing the subset of the data from the HDF5 group/file that
        fall within the specified area of interest and satisfy the specified query.
        Columns are limited to the specified sequence of column names, along with
        `filename` (str) and `BEAM` (str) columns. Further, the query is applied to, and
        the columns are selected from, only the top-level subgroups that have names
        prefixed with ``"BEAM"`` and for which the ``beam_filter`` function returns
        ``True``.

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
    ...     group.attrs.create("description", "Coverage beam")
    ...     group = hdf5.create_group("BEAM1011")
    ...     group.create_dataset("agbd", data=[1.1715966, 1.630395, 3.5265787])
    ...     group.create_dataset("l2_quality_flag", data=[0, 1, 1], dtype="i1")
    ...     group.create_dataset("lat_lowestmode", data=[-1.82557, -9.82515, -1.82472])
    ...     group.create_dataset("lon_lowestmode", data=[12.06649, 12.06679, 12.06708])
    ...     group.create_dataset("sensitivity", data=[0.93, 0.96, 0.98])
    ...     group.attrs.create("description", "Full power beam")
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
    ...         (
    ...             gpd.GeoDataFrame(
    ...                 {
    ...                     name: pd.Series(data, name=name)
    ...                     for name, data in group.items()
    ...                 }
    ...             )
    ...             for group in hdf5.values()
    ...         ),
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
    constructing it from a features list, but typically, it might be obtained via the
    ``geopandas.read_file`` function:

    >>> aoi = gpd.GeoDataFrame.from_features(
    ...     [
    ...         {
    ...             "properties": {},
    ...             "geometry": {
    ...                 "type": "Polygon",
    ...                 "coordinates": [
    ...                     [
    ...                         [8.45, 2.35],
    ...                         [14.35, 2.35],
    ...                         [14.35, -4.15],
    ...                         [8.45, -4.15],
    ...                         [8.45, 2.35],
    ...                     ]
    ...                 ],
    ...             },
    ...         }
    ...     ]
    ... )

    We can now subset the data in the HDF5 file to points that fall within the AOI,
    selecting only the desired columns (i.e., named datasets within the HDF5 file),
    selecting only the coverage beams, and selecting only the rows that satisfy
    the specified query:

    >>> with h5py.File(bio) as hdf5:
    ...     gdf = subset_hdf5(
    ...         hdf5,
    ...         aoi=aoi,
    ...         lat_col="lat_lowestmode",
    ...         lon_col="lon_lowestmode",
    ...         beam_filter=is_coverage_beam,
    ...         columns=["agbd", "sensitivity"],
    ...         query="l2_quality_flag == 1 and sensitivity > 0.95",
    ...     )
    ...     # Since the source of our HDF5 file is an ``io.BytesIO``, we'll drop the
    ...     # `filename` column (which refers to the memory location of the
    ...     # ``io.BytesIO``, not a filename).
    ...     gdf.drop(columns=["filename"])
           agbd  sensitivity                   geometry
    0  1.116093         0.99  POINT (12.06707 -1.82471)

    Note that the resulting ``geopandas.GeoDataFrame`` contains only the specified
    coverage `BEAM`s, specified columns (`agbd` and `sensitivity`), and only the
    rows (only 1 from each "beam" in this example) that have a geometry that falls
    within the AOI and also satisfy the query
    (i.e., `l2_quality_flag == 1` and `sensitivity > 0.95`).

    Note also that although the `l2_quality_flag` was specified in the query, it does
    not appear in the result because it was not specified in the sequence of column
    names.  This means that the query is not limited to refering to only names given in
    the sequence of column names, but may refer to any of the dataset names within the
    `"BEAM*"` groups.
    """

    def subset_beam(beam: h5py.Group) -> gpd.GeoDataFrame:
        """Subset an individual `"BEAM*"` group as described above."""

        # Project only the columns specified by the caller.
        # => SELECT col1, col2, ..., colN FROM beam

        # Avoid duplicating the coord columns, in case the caller also lists
        # them with the other columns, while also maintaining the column
        # ordering given by the caller.
        coord_columns = [col for col in (lon_col, lat_col) if col not in columns]
        projector = h5py_pandas_projector(beam)
        projection = projector[[*columns, *coord_columns]]

        # Filter rows, if a query was specified.
        # => WHERE condition
        df = projection.query(query, resolvers=[projector]) if query else projection

        # Create a GeoDataFrame from the subsetted data, and clip to the AOI.
        # => AND ST_Contains(aoi, geometry)
        return gpd.GeoDataFrame(
            # Drop coord columns that were NOT specified in the columns list
            df.drop(columns=coord_columns),
            geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
            crs=aoi.crs,
            copy=False,
        ).clip(aoi)

    beams = (
        group
        for name, group in hdf5.items()
        if name.startswith("BEAM") and beam_filter(group)
    )
    beams_gdf = pd.concat(map(subset_beam, beams), ignore_index=True, copy=False)
    beams_gdf.insert(0, "filename", os.path.basename(hdf5.file.filename))

    return cast(gpd.GeoDataFrame, beams_gdf)


def write_subset(infile, gdf):
    """
    Write GeoDataFrame to Flatgeobuf
    TODO: What's the most efficient format?
    """
    outfile = infile.replace(".h5", ".fgb")
    gdf.to_file(outfile, driver="FlatGeobuf")

    return outfile
