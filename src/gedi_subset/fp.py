"""Higher-order functions.

The `fp` (Functional Programming) module is along the lines of the standard
`functools` module, providing higher-order functions for easily constructing
new functions from other functions, for writing more declarative code.
"""

from collections.abc import Callable


def safely[**P, T](
    f: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs,
) -> T | Exception:
    """Safely call a function that might raise an exception.

    Invoke `f` with the specified arguments, but if `f` raises an exception,
    return the exception rather than raising it.

    NOTE: This is purposely _not_ written as a decorator, as it would cause a
    decorated function to have a type signature with a return type that differs
    from the resulting function, which could lead to confusion.

    Parameters
    ----------
    f
        Callable that might raise an exception.
    *args
        Positional arguments acceptable to `f`.
    **kwargs
        Keyword argumantes acceptable to `f`.

    Returns
    -------
    T | Exception
        Either the value return from calling `f` with the specified arguments,
        or the exception caught from `f`, if `f` raised one.

    Examples
    --------
    Using division by zero as an example, notice how "safe" division simply
    returns an instance of `ZeroDivisionError` rather than raising it:

    >>> from operator import truediv

    >>> safely(truediv, 4, 2)
    2.0
    >>> safely(truediv, 1, 0)
    ZeroDivisionError('division by zero')
    """
    try:
        return f(*args, **kwargs)
    except Exception as e:
        return e
