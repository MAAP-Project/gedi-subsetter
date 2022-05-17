"""Impure, safe wrappers of functions from the `os` module and sub-modules.

Wrappers are named the same as the functions they wrap, and expect the same
arguments, but never throw exceptions.  Instead, they return a value of the type
returned by the wrapped function, but wrapped in an `IOResultE`.

Functions:

- exists wraps os.path.exists and returns IOResultE[bool]
- remove wraps os.remove and returns IOResultE[None]
"""

import os
import os.path
from typing import TypeAlias, Union

from returns.io import IOResultE, impure_safe

StrPath: TypeAlias = Union[str, os.PathLike[str]]

exists = impure_safe(os.path.exists)


def remove(path: StrPath) -> IOResultE[None]:
    return impure_safe(os.remove)(path)
