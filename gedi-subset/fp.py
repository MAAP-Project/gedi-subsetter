"""Higher-order functions, generally curried for composition.

The `fp` (Functional Programming) module is along the lines of the standard
`functools` module, providing higher-order functions for easily constructing
new functions from other functions, for writing more declarative code.
Since the functions in this module are curried, there's no need to use
`functools.partial` for partially binding arguments.
"""
import builtins
from typing import Callable, Iterable, TypeVar, cast

from returns.curry import partial
from returns.maybe import Maybe, Nothing, Some

_A = TypeVar("_A")
_B = TypeVar("_B")


def filter(predicate: Callable[[_A], bool]) -> Callable[[Iterable[_A]], Iterable[_A]]:
    """Return a callable that accepts an iterable and returns an iterator that
    yields only the items of the iterable for which `predicate(item)` is `True`.
    Strictly curried to allow composition without the use of `functools.partial`.

    >>> list(filter(lambda x: x % 2 == 0)([1, 2, 3, 4, 5]))
    [2, 4]
    """
    return partial(builtins.filter, predicate)


def find(predicate: Callable[[_A], bool]) -> Callable[[Iterable[_A]], Maybe[_A]]:
    """Return a callable that accepts an iterable and returns the first item of the
    iterable (in a `Some`) for which `predicate` returns `True`; otherwise `Nothing`.

    >>> find(bool)([])
    <Nothing>
    >>> find(lambda x: x > 42)([19, 2, 42, 55, 45])
    <Some: 55>
    >>> find(lambda x: x > 99)([19, 2, 42, 55, 45])
    <Nothing>
    """

    def go(xs: Iterable[_A]) -> Maybe[_A]:
        for x in xs:
            if predicate(x):
                return Some(x)
        return Nothing

    return go


def always(a: _A) -> Callable[..., _A]:
    """Return the kestrel combinator ("constant" function).

    Return a callable that accepts exactly one argument of any type, but always
    returns the value `a`.

    >>> K(42)(0)
    42
    >>> K(42)('foo')
    42
    """
    return lambda _: a


def map(f: Callable[[_A], _B]) -> Callable[[Iterable[_A]], Iterable[_B]]:
    """Return a callable that accepts an iterable and returns an iterator that
    yields `f(item)` for each item in the iterable.

    >>> list(map(lambda x: 2 * x)([1, 2, 3]))
    [2, 4, 6]
    """
    return cast(Callable[[Iterable[_A]], Iterable[_B]], partial(builtins.map, f))
