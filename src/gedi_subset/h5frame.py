from __future__ import annotations

import functools
import re
import typing as t
from collections.abc import Iterable, Mapping

import h5py
import numpy as np
import pandas as pd

NAME_INDEX_PATTERN = re.compile(
    r"(?P<name>\w+(?:/\w+)*)\[(?P<index>-?\d+)\]",
    re.IGNORECASE,
)
NAME_SLICE_PATTERN = re.compile(
    r"(?P<name>\w+(?:/\w+)*)\[(?P<start>-?\d+)?:(?P<end>-?\d+)?\]",
    re.IGNORECASE,
)


class h5py_pandas_projector(dict):
    """Select (project) h5py Datasets from an h5py Group into a pandas data structure.

    A projector treats an h5py Group logically as a pandas DataFrame (or more
    generally, a relational table), specifically to support column selection
    (projection, in relational algebra parlance) via basic, square-bracket
    (`[]`) indexing, much like that described in
    [pandas indexing basics](https://pandas.pydata.org/pandas-docs/stable/user_guide/indexing.html#basics).

    Columns are represented by datasets within the group.  Datasets at all
    levels within the group are treated as if "flattened", such that every
    dataset (recursively) within the group is treated logically as a column,
    where the relative paths (names) of the datasets are used as column names.

    In particular, a projector supports the following types of `[]` indexing,
    where `"name"` is the (relative) name of a dataset within the projector's
    backing group:

    |Selection (projection)          |Return Value Type
    |:-------------------------------|:----------------
    |`projector["name"]`             |`pandas.Series` (1D dataset) or `pandas.DataFrame` (2D dataset)
    |`projector["name[index]"]`      |`pandas.Series` (2D dataset) or raises `ValueError`
    |`projector["name[slice]"]`      |`pandas.DataFrame` (2D dataset) or raises `ValueError`
    |`projector[[key_1, ..., key_n]]`|`pandas.DataFrame` (possibly with no columns)

    For full details, all of these types of indexing are thoroughly illustrated
    in the examples below.

    Parameters
    ----------
    group
        HDF5 group to use as the backing store for this projector.

    Examples
    --------
    In the following examples, assume we have an HDF5 file with the following
    hierarchy:

    ```plain
    +-- BEAM0000/ (group)
        +-- agbd: [1.271942, 1.3311168, 1.1160929]
        +-- land_cover_data/ (sub-group)
            +-- landsat_treecover: [55.0, 81.0, 51.0]
        +-- lat_lowestmode: [-1.82556, -4.82514, -1.82471]
        +-- lon_lowestmode: [12.06648, 12.06678, 12.06707]
        +-- quality_flag: [0, 1, 1]
        +-- rh: [[1.86, 1.94], [2.27, 2.39], [1.98, 2.09]]
        +-- sensitivity: [0.9, 0.97, 0.99]
    ```

    The following code constructs the example hierarchy shown above, so that we
    can use the data to illustrate this projector's capabilities farther below.
    In normal usage, we would typically read from the filesystem or object
    storage:

    >>> import io
    >>> import geopandas as gpd
    >>> import pandas as pd

    >>> source = io.BytesIO()

    >>> with h5py.File(source, "w") as hdf5:  # doctest: +ELLIPSIS
    ...     group = hdf5.create_group("BEAM0000")
    ...     group.create_dataset("agbd", data=[1.271942, 1.3311168, 1.1160929])
    ...     subgroup = group.create_group("land")
    ...     subgroup.create_dataset("treecover", data=[55.0, 81.0, 51.0])
    ...     group.create_dataset("latitude", data=[-1.82556, -9.82514, -1.82471])
    ...     group.create_dataset("longitude", data=[12.06648, 12.06678, 12.06707])
    ...     group.create_dataset("quality_flag", data=[0, 1, 1], dtype="i1")
    ...     group.create_dataset("rh", data=[[1.86, 1.94], [2.27, 2.39], [1.98, 2.09]])
    <HDF5 dataset "agbd": ...>
    <HDF5 dataset "treecover": ...>
    <HDF5 dataset "latitude": ...>
    <HDF5 dataset "longitude": ...>
    <HDF5 dataset "quality_flag": ...>
    <HDF5 dataset "rh": ...>

    To make it easier to see what subsetting the HDF5 file will do, let's take a
    look at how we might expect the entirety of the data within the `BEAM0000`
    group to appear when flattened into a `pandas.DataFrame`:

    ```plain
           agbd  land/treecover  latitude  longitude  quality_flag            rh
    0  1.271942            55.0  -1.82556   12.06648             0  [1.86, 1.94]
    1  1.331117            81.0  -9.82514   12.06678             1  [2.27, 2.39]
    2  1.116093            51.0  -1.82471   12.06707             1  [1.98, 2.09]
    ```

    This projector is intended to simplify the process of constructing a
    Pandas DataFrame from datasets within an HDF5 file.

    The simplest way to do so is to create a projector for a group (or even a
    file), then index the projector with a sequence of desired columns, which
    will be populated from datasets within the projector's backing group,
    specifying dataset paths relative to the group:

    >>> with h5py.File(source) as h5:
    ...     # Create projector backed by top-level group named "BEAM0000" within h5 file
    ...     projector = h5py_pandas_projector(h5["BEAM0000"])
    ...     # Project datasets "agbd" & "land/treecover" from "BEAM0000" into DataFrame
    ...     df = projector[["agbd", "land/treecover"]]
    ...     df
           agbd  land/treecover
    0  1.271942            55.0
    1  1.331117            81.0
    2  1.116093            51.0

    Subsequently, we may then query the resulting dataframe using the `query`
    method, specifying the projector in the method's `resolver` parameter:

    >>> with h5py.File(source) as h5:
    ...     projector = h5py_pandas_projector(h5["BEAM0000"])
    ...     df = projector[["agbd", "land/treecover"]]
    ...     df.query("quality_flag == 1", resolvers=[projector])
           agbd  land/treecover
    1  1.331117            81.0
    2  1.116093            51.0

    For nested datasets, backtick quoting is supported within the query string,
    which is necessary to prevent the query parser from interpreting forward
    slashes (`/`) as the division operator:

    >>> with h5py.File(source) as h5:
    ...     projector = h5py_pandas_projector(h5["BEAM0000"])
    ...     df = projector[["agbd", "land/treecover"]]
    ...     df.query("quality_flag == 1 & `land/treecover` > 80", resolvers=[projector])
           agbd  land/treecover
    1  1.331117            81.0

    To conveniently handle 2D datasets, both indexing and slicing notations may
    be used for selecting the desired columns, or even all columns, particulary
    when explicitly enumerating all of them would be tedious.

    For example, the `rh` dataset shown above is a 2D dataset.  If we want to
    extract only a particular column, we may use standard integer indexing
    notation:

    >>> with h5py.File(source) as h5:
    ...     projector = h5py_pandas_projector(h5["BEAM0000"])
    ...     df = projector[["agbd", "rh[0]"]]
    ...     df
           agbd  rh[0]
    0  1.271942   1.86
    1  1.331117   2.27
    2  1.116093   1.98

    NOTE: Negative indexing is also supported, but it is assumed that use of a
    negative index indicates that the number columns in a 2D dataset is not
    known advance, thus the name of the resulting column in the dataframe
    retains the negative index rather than resolving it to the 0-based index.
    This allows selecting from the dataframe with the very same negative index:

    >>> with h5py.File(source) as h5:
    ...     projector = h5py_pandas_projector(h5["BEAM0000"])
    ...     df = projector[["agbd", "rh[-1]"]]
    ...     df
           agbd  rh[-1]
    0  1.271942    1.94
    1  1.331117    2.39
    2  1.116093    2.09

    Slice syntax is also supported, excluding the use of a step size.  Thus,
    slices of only the following forms are supported: `[:]`, `[start:]`,
    `[start:end]`, or `[:end]`.  In all cases, the relevant columns are
    expanded into the resulting dataframe:

    >>> with h5py.File(source) as h5:
    ...     projector = h5py_pandas_projector(h5["BEAM0000"])
    ...     df = projector[["agbd", "rh[:]"]]
    ...     df
           agbd  rh[0]  rh[1]
    0  1.271942   1.86   1.94
    1  1.331117   2.27   2.39
    2  1.116093   1.98   2.09

    >>> with h5py.File(source) as h5:
    ...     projector = h5py_pandas_projector(h5["BEAM0000"])
    ...     df = projector[["agbd", "rh[:]"]]
    ...     df.query("rh[0] >= 2.0", resolvers=[projector])
           agbd  rh[0]  rh[1]
    1  1.331117   2.27   2.39

    Finally, to project all of the data from a 2D dataset, without expanding the
    columns into separate Series, simply use the name of the dataset without any
    indexing or slicing notation:

    >>> with h5py.File(source) as h5:
    ...     projector = h5py_pandas_projector(h5["BEAM0000"])
    ...     df = projector[["agbd", "rh"]]
    ...     df
           agbd            rh
    0  1.271942  [1.86, 1.94]
    1  1.331117  [2.27, 2.39]
    2  1.116093  [1.98, 2.09]

    >>> with h5py.File(source) as h5:
    ...     projector = h5py_pandas_projector(h5["BEAM0000"])
    ...     df = projector[["agbd", "rh"]]
    ...     df.query("rh[0] >= 2.0", resolvers=[projector])
           agbd            rh
    1  1.331117  [2.27, 2.39]

    Note, however, when a 2D dataset is given as a singular key index (i.e., not
    as an element of a list of keys), the dataset is expanded into distinct
    columns:

    >>> with h5py.File(source) as h5:
    ...     projector = h5py_pandas_projector(h5["BEAM0000"])
    ...     rh = projector["rh"]
    ...     rh
          0     1
    0  1.86  1.94
    1  2.27  2.39
    2  1.98  2.09

    Further, the column "names" in this case are simply the 0-based integer
    column indices.  This enables indexing of columns with integer indexing:

    >>> rh[0]
    0    1.86
    1    2.27
    2    1.98
    Name: 0, dtype: float64

    This is necessary in order to support such indexing within DataFrame
    query strings, which would otherwise not work, but notice that in such
    cases, we are not explicitly indexing the projector with a singular string,
    but rather, the underlying query parser is doing so _implicitly_:

    >>> with h5py.File(source) as h5:
    ...     projector = h5py_pandas_projector(h5["BEAM0000"])
    ...     df = projector[["agbd", "rh"]]
    ...     df.query("rh[0] < 2.0", resolvers=[projector])
           agbd            rh
    0  1.271942  [1.86, 1.94]
    2  1.116093  [1.98, 2.09]

    Further, notice that although the query includes the subexpression `rh[0]`,
    which implicitly evaluates `projector["rh"][0]`, and thus implicitly
    constructs a DataFrame containing the distinct columns of `rh` (to allow
    selecting column 0 in the query), we explicitly used `"rh"` (along with
    `"agbd"`) to create the DataFrame `df`, and thus the DataFrame does not
    include `rh` expanded into separate columns.
    """

    def __init__(self, group: h5py.Group):
        self._group = group

    @t.override
    def __getitem__(self, key: Iterable[str], /) -> pd.Series | pd.DataFrame:
        expand = isinstance(key, str)
        keys = [key] if expand else key
        return _to_pandas(_project(self._group, *keys), expand=expand)


def _project(group: h5py.Group, *keys: str) -> Mapping[str, np.ndarray]:
    """Project (select) h5py.Datasets from an h5py.Group.

    Merges results of invoking `_project_one` for each key in `keys` into a
    single mapping.

    Parameters
    ----------
    group
        Group to project (select) datasets from.
    keys
        Zero or more keys, each referring to either a full dataset (either 1D or
        2D) or specific columns of a 2D dataset.

    Returns
    -------
    collections.abc.Mapping
        Mapping from dataset name (path relative to `group`), or dataset name
        with column index, to numpy array of data from the named dataset or
        dataset column.

    Raises
    ------
    KeyError
        if there is no dataset within the group that has a (relative) name given
        by a key (excluding any indexing or slicing syntax present in the key)
    ValueError
        if a dataset is 1D, but the key includes indexing or slicing syntax
        (which is valid only for 2D datasets)
    """
    return dict(entry for k in keys for entry in _project_one(group, k).items())


def _project_one(group: h5py.Group, key: str) -> Mapping[str, np.ndarray]:
    """Project (select) h5py.Dataset (fully or specific columns) from a h5py.Group.

    The specified group is treated logically like a relational table with all
    datasets (both top-level and nested) treated logically as columns within the
    table.  Column names are given by the relative paths of the datasets within
    the group.

    For example, assume we have a group with the following hierarchy:

    ```plain
    +-- BEAM0000/ (group)
        +-- agbd: [1.271942, 1.3311168, 1.1160929]
        +-- land/ (sub-group)
            +-- treecover: [55.0, 81.0, 51.0]
        +-- lat_lowestmode: [-1.82556, -4.82514, -1.82471]
        +-- lon_lowestmode: [12.06648, 12.06678, 12.06707]
        +-- rh: [[1.86, 1.94], [2.27, 2.39], [1.98, 2.09]]
    ```

    In this case, the group would logically represent a relational table (named
    "BEAM0000"), with the following columns:

    - agbd
    - land/treecover
    - lat_lowestmode
    - lon_lowestmode
    - rh (2D)

    Note how the nested "treecover" dataset is logically treated as though it
    exists at the top level of the root group (BEAM0000), and it's column name
    is simply the entire (relative) path of the dataset ("land/treecover").

    For 1D datasets, the specified key must be exactly the name (relative path)
    of the (possibly nested) dataset.  However, for 2D datasets, the key may be
    either the name or the name with indexing or slicing notation.

    When the key is a name only, the result is a dictionary containing only the
    name and data for the named dataset, regardless of dimensionality.

    However, for 2D datasets, when the key includes indexing or slicing
    notation, the resulting dictionary may contain zero or more entries.  See
    the examples for details.

    Parameters
    ----------
    group
        HDF5 group from which to project one or more columns of data.  The group
        is treated logically like a relational table, where all nested datasets
        (flattened) are treated logically as individual columns within the
        logical table.
    key
        String naming an HDF5 dataset within `group`.  Logically, the key names
        a column within the logical relational table represented by `group`.

        It may name a dataset at the top of the group, or nested within the
        group.  Either way, the name within this key is a relative path of the
        dataset within the group, excluding a leading slash (`/`).

        The key may consist solely of the relative dataset name (path) or a name
        followed by indexing/slicing syntax.  When the key is a name only (e.g.,
        `"agbd"` or `"land/treecover"`), the dataset may be either 1D or 2D.
        When indexing/slicing syntax is included (e.g., `"rh[0]"`, `"rh[1:]"`),
        the dataset must be 2D, in which case the indicated columns from the 2D
        dataset are projected.

    Returns
    -------
    projection
        A dictionary mapping names to one or more columns of numpy arrays.  When
        `key` is solely the name (path) of a dataset within `group`, the
        dictionary contains a single entry, where the key is the value of `key`
        and the value is the numpy array of data (either 1D or 2D) from the
        dataset.  When the key includes indexing or slicing notation, the
        dictionary may contain zero or more entries (see examples).

    Raises
    ------
    KeyError
        if there is no dataset within the group that has a (relative) name given
        by the key (excluding any indexing or slicing syntax present in the key)
    ValueError
        if the dataset is 1D, but the key includes indexing or slicing syntax
        (which is valid only for 2D datasets)

    Examples
    --------
    Given a group (in this case an h5py.File, which is a subclass of
    h5py.Group), we may project either a 1D dataset, a 2D dataset (in its
    entirety, as a 2D array), or specific columns from a 2D dataset (as
    individual 1D arrays):

    >>> import io
    >>> import pandas as pd

    >>> data = io.BytesIO()

    >>> with h5py.File(data, "w") as hdf5:  # doctest: +ELLIPSIS
    ...     hdf5.create_dataset("agbd", data=[1.2719421, 1.3311168, 1.1160929])
    ...     hdf5.create_dataset("rh", data=[[1.86, 1.94], [2.27, 2.39], [1.98, 2.09]])
    <HDF5 dataset "agbd": ...>
    <HDF5 dataset "rh": ...>

    Projecting a 1D dataset returns a single column consisting of a 1D array:

    >>> with h5py.File(data) as h5:
    ...     _project_one(h5, "agbd")
    {'agbd': array([1.2719421, 1.3311168, 1.1160929])}

    Projecting a 2D dataset returns a single column consisting of a 2D array:

    >>> with h5py.File(data) as h5:
    ...     _project_one(h5, "rh")
    {'rh': array([[1.86, 1.94],
           [2.27, 2.39],
           [1.98, 2.09]])}

    Indexing a 2D array returns a single column consisting of a 1D array
    containing the corresponding column from the underlying 2D array:

    >>> with h5py.File(data) as h5:
    ...     _project_one(h5, "rh[0]")
    {'rh[0]': array([1.86, 2.27, 1.98])}

    Note that indexing with a negative index also produces a single column with
    a 1D array, but the name of the column _retains_ the negative index rather
    than resolving to the associated non-negative position from the beginning of
    the array.

    This supports being able to use the same negative indexing elsewhere for
    cases where the number of columns in the 2D dataset is not known in advance,
    which would make having to use the corresponding non-negative index
    cumbersome or inconvenient, due to the additional logic required to
    "discover" the real index values.

    For example, the following shows how to reference the last column of a 2D
    dataset without having to know how many columns it contains.  Since we don't
    necessarily care how many there are, we can use an index of `-1` to indicate
    the last column, regardless of the actual index:

    >>> with h5py.File(data) as h5:
    ...     _project_one(h5, "rh[-1]")
    {'rh[-1]': array([1.94, 2.39, 2.09])}

    Using slicing notation with a 2D array will slice the columns of the 2D
    array into distinct columns in the result.  For example, specifying a "full"
    slice results in every column of the 2D array appearing as a separate entry:

    >>> with h5py.File(data) as h5:
    ...     _project_one(h5, "rh[:]")
    {'rh[0]': array([1.86, 2.27, 1.98]), 'rh[1]': array([1.94, 2.39, 2.09])}

    Note that when a slice is completely out of bounds, the result is an empty
    projection:

    >>> with h5py.File(data) as h5:
    ...     _project_one(h5, "rh[2:]")
    {}
    """
    name, projector = _parse_key(key)
    dataset = _fetch_dataset(group, name)

    if projector is None:
        # The key is simply a name, so return a single "column", either 1D or 2D.
        return {name: dataset[:]}

    if dataset.ndim == 1:
        msg = f"array is 1D; indexing and slicing are not permitted: {key}"
        raise ValueError(dataset, msg)

    return {
        f"{name}[{i}]": dataset[:, i]
        for i in _compute_indices(projector, length=dataset.shape[1])
    }


def _fetch_dataset(group: h5py.Group, name: str) -> h5py.Dataset:
    """Fetch a Dataset by name from a Group.

    Parameters
    ----------
    group
        Group to fetch a dataset from.
    name
        Name of dataset relative to `group`.

    Returns
    -------
    h5py.Dataset
        Dataset named `name` relative to `group`.

    Raises
    ------
    KeyError
        if `group` does not contain a dataset with the relative name `name`
    """
    if not isinstance(dataset := group.get(name), h5py.Dataset):
        msg = f"dataset not found in group {group.name!r}: {name}"
        raise KeyError(name, msg)

    return dataset


def _parse_key(key: str) -> tuple[str, int | slice | None]:
    """Parse key into a name and optionally an index or slice.

    Examples
    --------
    >>> _parse_key("x")
    ('x', None)
    >>> _parse_key("x[0]")
    ('x', 0)
    >>> _parse_key("x[-1]")
    ('x', -1)
    >>> _parse_key("x[:]")
    ('x', slice(None, None, None))
    >>> _parse_key("x[1:]")
    ('x', slice(1, None, None))
    >>> _parse_key("x[1:10]")
    ('x', slice(1, 10, None))
    >>> _parse_key("x[:10]")
    ('x', slice(None, 10, None))
    """
    name = _smudge_name(key)

    if match := re.fullmatch(NAME_INDEX_PATTERN, name):
        # We have a name of the form "name[index]".
        return match["name"], int(match["index"])

    if match := re.fullmatch(NAME_SLICE_PATTERN, name):
        # We have a name of the form "name[start:end]", where `start` and
        # `end` are both optional. Using default="" ensures `start` and/or
        # `end` are set to empty strings rather than None, when not given.
        name, start, end = match.groups(default="")
        columns_slice = slice(int(start) if start else None, int(end) if end else None)

        return name, columns_slice

    return name, None


@functools.cache
def _smudge_name(name: str) -> str:
    """Smudge previously cleaned backtick-quoted tokens.

    Within Pandas query strings, backticks must be used to surround names
    (tokens) that contain characters that are not permitted within Python
    identifiers (variable names) -- basically any character that is neither an
    underscore nor an alphanumeric character.  In such cases, during parsing of
    query expressions, Pandas "cleans" such backtick-quoted tokens (names) in
    order to transform such names into valid Python identifiers.

    In particular, during the "cleaning" process, Pandas adds the prefix
    `BACKTICK_QUOTED_STRING_` to the name/token, while also replacing illegal
    characters with legal substitutions, such as replacing a slash (`/`) with
    the characters `_SLASH_`, among other similar replacements.  This function
    simply reverses the "cleaning" process, by "smudging" cleaned names.  In the
    case of a non-cleaned name, it is returned as is.

    Examples
    --------
    >>> _smudge_name("BACKTICK_QUOTED_STRING_path_SLASH_to_SLASH_dataset")
    'path/to/dataset'
    >>> _smudge_name("valid_identifier")
    'valid_identifier'

    See Also
    --------
    pandas.core.computation.parsing.clean_backtick_quoted_toks
    """
    return functools.reduce(
        lambda name, tok: name.replace(tok, _token_table()[tok]),
        _token_table().keys(),
        name.removeprefix("BACKTICK_QUOTED_STRING_"),
    )


@functools.cache
def _token_table() -> Mapping[str, str]:
    """Return mapping from "cleaned" token to original (invalid/dirty) token.

    Examples
    --------
    >>> tt = _token_table()
    >>> tt["_SLASH_"]
    '/'
    >>> tt["_LSQB_"]
    '['
    >>> tt["_RSQB_"]
    ']'
    """
    import token

    num_to_tok = {num: tok for tok, num in token.EXACT_TOKEN_TYPES.items()}

    return {
        f"_{name}_": num_to_tok[num]
        for num, name in token.tok_name.items()
        if num in num_to_tok
    }


def _compute_indices(projector: int | slice, *, length: int) -> tuple[int, ...]:
    """Produce tuple of all indices of a sequence indicated by a projector.

    Arguments
    ---------
    projector
        Value indicating which elements from a sequence of length `length` to
        _project_ (select), as in a relational algebra projection.  An integer
        value specifies a single, 0-based index, with negative indexing
        permitted as well.  A slice value indicates zero or more indices to
        project.
    length
        The length of the sequence of elements to project from, clipping the
        resulting indices accordingly.

    Returns
    -------
    indices
        Possibly empty tuple of indices indicated by `projector`.  When
        `projector` is an integer, a tuple containing only the integer.  The
        tuple may be empty if the slice is completely clipped by the `length`.

    Raises
    ------
    ValueError
        if `length` is negative
    IndexError
        if `projector` is an integer outside the inclusive range [-length, length - 1]

    Examples
    --------
    With a single integer projector, we generally expect to get back the same
    integer as the sole element of a tuple:

    >>> _compute_indices(0, length=1)
    (0,)
    >>> _compute_indices(-1, length=1)
    (-1,)

    With a slice projector, we get all indices indicated by the slice:

    >>> _compute_indices(slice(None, None, None), length=5)
    (0, 1, 2, 3, 4)
    >>> _compute_indices(slice(3, None, None), length=5)
    (3, 4)

    However, when the slice starts with a negative value, we retain the
    negative numbering, under the assumption that use of a negative index
    indicates that the user does not know the length in advance, but rather
    simply wants the last _n_ values; for example, the last 2 elements:

    >>> _compute_indices(slice(-2, None, None), length=5)
    (-2, -1)

    By retaining the negative numbering (`(-2, -1)` rather than `(3, 4)` in this
    case), the user may then also use the negative numbering later, so that the
    user never needs to inspect the result to know what the 0-based indices are.

    When the length is shorter than indicated by the negative index, the indices
    are clipped appropriately.  For example, specifying the last 10 indices from
    a sequence of length 5, will return only 5 indices, not 10:

    >>> _compute_indices(slice(-10, None, None), length=5)
    (-5, -4, -3, -2, -1)

    Finally, use of a step or stride value in a slice is supported as well:

    >>> _compute_indices(slice(0, 10, 2), length=100)
    (0, 2, 4, 6, 8)

    Note that the end value of the slice is _exclusive_, just as with a range,
    which is why `8` is the last value in the resulting tuple above, not `10`.
    """

    if length < 0:
        raise ValueError(length, "length must be non-negative")

    match projector:
        case int() as i if i < -length or length - 1 < i:
            msg = f"index must be in the closed range [-{length}, {length - 1}]"
            raise IndexError(i, msg)
        case int() as i:
            return (i,)
        case slice() as s:
            use_negatives = s.start is not None and s.start < 0
            indices = tuple(range(*s.indices(length)))
            return tuple(i - length for i in indices) if use_negatives else indices


def _to_pandas(
    projection: Mapping[str, np.ndarray],
    *,
    expand: bool = False,
) -> pd.Series | pd.DataFrame:
    """Convert projection of columns to Series or DataFrame.

    Parameters
    ----------
    projection
        Mapping from column name to column data.
    expand
        Indicates whether or not to expand columns of a 2D array into distinct
        columns of a DataFrame.

    Examples
    --------
    When a projection consists solely of a single 1D array, a Series is
    returned:

    >>> import numpy as np
    >>> projection = {"rh": np.array([1.86, 2.27, 1.98])}
    >>> _to_pandas(projection)
    0    1.86
    1    2.27
    2    1.98
    Name: rh, dtype: float64

    When there are multiple arrays, a DataFrame is returned:

    >>> projection = {
    ...     "rh[0]": np.array([1.86, 2.27, 1.98]),
    ...     "rh[1]": np.array([1.94, 2.39, 2.09]),
    ... }
    >>> _to_pandas(projection)
       rh[0]  rh[1]
    0   1.86   1.94
    1   2.27   2.39
    2   1.98   2.09

    In the case of a 2D array, by default (i.e., `expand=False`), a single
    column (Series) is constructed, with each element of the column consisting
    of a row of elements of the array:

    >>> projection = {"rh": np.array([[1.86, 1.94], [2.27, 2.39], [1.98, 2.09]])}
    >>> _to_pandas(projection)
    0    [1.86, 1.94]
    1    [2.27, 2.39]
    2    [1.98, 2.09]
    Name: rh, dtype: object

    However, passing `expand=True` causes the columns to be expanded into
    individual Series, resulting in a DataFrame:

    >>> df = _to_pandas(projection, expand=True)
    >>> df
          0     1
    0  1.86  1.94
    1  2.27  2.39
    2  1.98  2.09

    Note that in this case, the column labels are simply the integer indices,
    thus allowing selection of individual column using regular indexing syntax:

    >>> df[0]
    0    1.86
    1    2.27
    2    1.98
    Name: 0, dtype: float64

    Finally, an empty projection produces an empty DataFrame:

    >>> _to_pandas({})
    Empty DataFrame
    Columns: []
    Index: []
    """

    if not projection:
        return pd.DataFrame()

    if len(projection) > 1:
        objs = (
            _to_pandas({name: array}, expand=expand)
            for name, array in projection.items()
        )
        return pd.concat(objs, axis=1, copy=False)

    # We have only 1 column in the projection, so get its name and value.
    (name, array), *_ = projection.items()

    if array.ndim == 1:
        # Always return a Series for a 1D array.
        return pd.Series(array, name=name, copy=False)

    # We have a 2D array, which we may want to expand into separate columns of
    # a DataFrame or not.  If not, we must convert it into a list of its rows in
    # order to produce a Series where each element is a row of the 2D array.
    return (
        pd.DataFrame(array, copy=False)
        if expand
        else pd.Series(array.tolist(), name=name, copy=False)
    )
