from __future__ import annotations

import re
from typing import Any, Iterable, Literal, cast, overload

import h5py
import pandas as pd


class H5DataFrame(pd.DataFrame):
    """Pandas DataFrame backed by an HDF5 File/Group.

    Parameters
    ----------
    group: h5py.Group
        HDF5 group to use as the backing store for this DataFrame.  This may be
        either an open h5py.File or an h5py.Group, which is the superclass of
        h5py.File.

    Examples
    --------
    Constructing an H5DataFrame from an h5py.File operates lazily.  Initially,
    no data is loaded from the file.  In the following examples, assume the
    file ``"data.h5"`` is a non-empty HDF5 file, with a Group and Datasets.

    >>> import h5py
    >>> with h5py.File("data.h5") as h5:  # doctest: +SKIP
    ...     df = H5DataFrame(h5)
    ...     df
    Empty H5DataFrame
    Columns: []
    Index: []

    Although use of a context manager is strongly recommended, as in the example
    above, for simplicity, the remaining examples do not do so.

    In order to load data from a file, you must explicitly reference the desired
    data by name or path.  Since HDF5 files are hierarchical, names/paths may
    refer to either a Group or a Dataset.

    Referencing a Group results in another H5DataFrame, which will also load
    lazily:

    >>> h5 = h5py.File("data.h5")  # doctest: +SKIP
    >>> df = H5DataFrame(h5)  # doctest: +SKIP
    >>> df["group"]  # doctest: +SKIP
    Empty H5DataFrame
    Columns: []
    Index: []

    Referencing a 1D Dataset produces a pandas.Series, an _also_ inserts the
    series as a column into the H5DataFrame:

    >>> group_df = df["group"]  # doctest: +SKIP
    >>> group_df  # doctest: +SKIP
    Empty H5DataFrame
    Columns: []
    Index: []

    >>> group_df["vector"]  # doctest: +SKIP
    0    <v0>
    1    <v1>
    ...
    Name: vector, Length: ..., dtype: ...

    >>> group_df  # doctest: +SKIP
         vector
    0      <v0>
    1      <v1>
    ...
    [... rows x 1 columns]

    Referencing a 2D Dataset will produce a standard pandas DataFrame and will
    _not_ update the H5DataFrame:

    >>> df = H5DataFrame(h5)  # doctest: +SKIP
    >>> group_df = df["group"]  # doctest: +SKIP
    >>> group_df["matrix"]  # doctest: +SKIP
         0  1  2  ...
    0   ...
    1   ...
    ...
    [... rows x ... columns]

    >>> group_df  # doctest: +SKIP
    Empty H5DataFrame
    Columns: []
    Index: []

    However, it is possible to reference the columns of a 2D Dataset in a way
    that automatically inserts the columns into this H5DataFrame:

    >>> group_df["matrix0"]  # doctest: +SKIP
    0    <v0>
    1    <v1>
    ...
    Name: vector, Length: ..., dtype: ...

    By using the pseudo-dataset name "matrix0", the 2D "matrix" dataset is
    retrieved, its column at index 0 is wrapped in a pandas Series, and the
    Series is inserted as a column named "matrix0" into this H5DataFrame (which
    works for all indices of the 2D Dataset):

    >>> group_df  # doctest: +SKIP
        matrix0
    0      <v0>
    1      <v1>
    ...
    [... rows x 1 columns]

    It is also possible to use the ``query`` method using an expression that
    references 1D Datasets, and the referenced Datasets will automatically be
    added as columns to this H5DataFrame, if not already present.

    To reference nested Datasets, use standard HDF5 paths containing forward
    slash (``"/"``) separators, relative to the group path.  Doing so will
    insert a column by the same relative name (including forward slashes) into
    this H5DataFrame.

    >>> df = H5DataFrame(h5)  # doctest: +SKIP
    >>> df["group/vector"]  # doctest: +SKIP
    0    <v0>
    1    <v1>
    ...
    Name: group/vector, Length: ..., dtype: ...

    NOTE: In order to use the name of a nested Dataset within a query
    expression, you must surround the name within backticks.  Otherwise, the
    slashes will be interpreted as division operators:

    >>> df.query("group/vector > 0.5")  # doctest: +SKIP
    ...
    pandas.core.computation.ops.UndefinedVariableError: name 'vector' is not defined

    Using backticks around the path prevents such unintended interpretation:

    >>> df.query("`group/vector` > 0.5")  # doctest: +SKIP
        group/vector
    0           <v0>
    1           <v1>
    ...

    Alternatively, "dot" notation is possible.  By using dots (periods) in place
    of slashes, backticks can be avoided.  Note, however, that column names will
    still contain slashes:

    >>> df.query("group.vector > 0.5")  # doctest: +SKIP
        group/vector
    0           <v0>
    1           <v1>
    ...
    """

    _metadata = ["_group", "_parent"]

    def __init__(self, group: h5py.Group, parent: "H5DataFrame" | None = None) -> None:
        super().__init__()

        if not isinstance(group, h5py.Group):
            raise ValueError(f"group must be an h5py.Group, not {type(group)}")
        if parent is not None and not isinstance(parent, H5DataFrame):
            raise ValueError(f"parent must be an H5DataFrame, not {type(group)}")

        self._group = group
        self._parent = parent

    def __contains__(self, key) -> bool:
        # Since we don't add columns to self during initialization, we must
        # override __contains__ in order to be able to resolve column names
        # during calls to `eval`.  Otherwise, `eval` will throw KeyErrors for
        # columns not yet loaded from our backing h5py.Group.
        return key in self.group or super().__contains__(key)

    def __getattr__(self, name: str) -> pd.Series:
        try:
            return self[name]
        except Exception:
            return super().__getattr__(name)

    def __getitem__(self, key):
        if isinstance(key, (str, bytes)):
            return self.__get_named_item(key)

        if isinstance(key, Iterable):
            # The key is possibly a "collection" of keys, so attempt to get the
            # column for each one, to make sure each has been read from our
            # backing h5py.Group and added as a column to self, if it's 1-D.
            items = {k: self.__getitem__(k) for k in key}.items()

            # If there are any 2-D values, raise an error, because when an
            # iterable key is specified, each item must result in a Series.
            if names := [k for k, v in items if isinstance(v, pd.DataFrame)]:
                raise TypeError(
                    f"The following dataset{' is' if len(names) == 1 else 's are'}"
                    f" 2-dimensional: {', '.join(names)}."
                    f" You so you must select a column by index."
                    f" (Examples: {names[0]}0, {names[0]}99)"
                )

        result = super().__getitem__(key)

        return self.__narrow(result) if isinstance(result, pd.DataFrame) else result

    def __get_named_item(self, key: str | bytes):
        key_ = key if isinstance(key, str) else key.decode("utf-8")

        if key_ in self.columns:
            return super().__getitem__(key_)
        if key_ in self.group:
            return self.__wrap_item(key_, self.group[key_])
        if key_.startswith("BACKTICK_QUOTED_STRING_"):
            path = key_[len("BACKTICK_QUOTED_STRING_") :].split("_SLASH_")
            return self["/".join(path)]

        if match := re.fullmatch(r"(?P<name>[a-zA-Z_]+)(?P<index>\d+)", key_):
            # `key` is of the form `<name><index>`, so assume `<name>` is the name of a
            # 2D dataset, retrieve the dataset, grab the column at index `<index>`, and
            # add it as a column to self.  For example, if `key` is `rh50`, attempt to
            # fetch `rh` and select column 50 from it, inserting the result as a column
            # named `rh50` into self.
            name, index = match.groups()
            return self.__wrap_item(key_, self[name][int(index)])

        return super().__getitem__(key_)

    def __wrap_item(self, key: str, value: h5py.Dataset | h5py.Group):
        if isinstance(value, h5py.Group):
            return H5DataFrame(value, self)
        if value.ndim == 2:
            return pd.DataFrame(value)
        if value.ndim != 1:
            return super().__getitem__(key)

        # If self has no rows (empty index), but has at least 1 column, we want our new
        # column to also have no rows.  This handles cases where columns were already
        # inserted, but where a query has discarded all rows.  If we were to then insert
        # a new, non-empty column, it would not be index-aligned (since the index is
        # empty), and thus would "expand" all previously removed rows, filling all
        # previously empty columns with NaN values.

        name = f"{self.relpath}/{key}".lstrip("/")

        if name not in self.root.columns:
            data = [] if self.index.empty and not self.columns.empty else value
            column = pd.Series(data, dtype=value.dtype)
            self.root.insert(len(self.root.columns), name, column)

        return self.root[name]

    def __narrow(self, df: pd.DataFrame) -> H5DataFrame:
        df.__class__ = H5DataFrame
        df._group = self._group
        df._parent = self._parent

        return cast(H5DataFrame, df)

    def __setitem__(self, key, value):
        if isinstance(value, pd.Series):
            return super().__setitem__(key, value)

    @property
    def group(self) -> h5py.Group:
        return self._group

    @property
    def parent(self) -> H5DataFrame | None:
        return self._parent

    @property
    def relpath(self) -> str:
        root_path = self.root.group.name
        self_path = self.group.name

        return (
            self_path[len(root_path) :].lstrip("/")
            if isinstance(root_path, str) and isinstance(self_path, str)
            else ""
        )

    @property
    def root(self) -> H5DataFrame:
        return self if self.parent is None else self.parent.root

    @overload
    def query(self, expr: str, *, inplace: Literal[True], **kwargs: Any) -> None: ...

    @overload
    def query(
        self, expr: str, *, inplace: Literal[False] = ..., **kwargs: Any
    ) -> H5DataFrame: ...

    def query(
        self,
        expr: str,
        *,
        inplace: bool = False,
        **kwargs: Any,
    ) -> H5DataFrame | None:
        # Insert self as a resolver since the built-in columns resolver won't resolve
        # columns that have not yet been loaded from the backing store.
        kwargs["resolvers"] = (self, *tuple(kwargs.get("resolvers", ())))
        result = super().query(expr, inplace=inplace, **kwargs)  # type: ignore

        return self.__narrow(result) if isinstance(result, pd.DataFrame) else result
