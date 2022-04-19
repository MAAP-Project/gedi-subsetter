import builtins
from typing import Callable, Iterable, TypeVar

from returns.curry import partial

_A = TypeVar("_A")
_B = TypeVar("_B")


def filter(predicate: Callable[[_A], bool]) -> Callable[[Iterable[_A]], Iterable[_A]]:
    """Properly typed and strictly curried form of builtins.filter"""
    return partial(builtins.filter, predicate)


def K(a: _A) -> Callable[..., _A]:
    """The kestrel combinator ("constant" function)"""
    return lambda _: a


def map(f: Callable[[_A], _B]) -> Callable[[Iterable[_A]], Iterable[_B]]:
    """Properly typed and strictly curried form of builtins.map"""
    return partial(builtins.map, f)
