from __future__ import annotations

import contextlib
import logging
import threading
import time
from datetime import UTC, datetime
from multiprocessing.context import BaseContext
from multiprocessing.managers import ValueProxy
from typing import TYPE_CHECKING, Callable, Generator

if TYPE_CHECKING:
    from maap.AWS import AWSCredentials

logger = logging.getLogger(__name__)


def log_credentials_expiration(creds: AWSCredentials) -> None:
    logger.info("Fetched AWS credentials expiring at %s", creds["expiration"])


@contextlib.contextmanager
def credentials_proxy(
    ctx: BaseContext,
    fetch_credentials: Callable[[], AWSCredentials],
    *,
    buffer_seconds: float = 5 * 60,  # 5 minutes
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Generator[ValueProxy["AWSCredentials"]]:
    """Context manager for AWS S3 credentials.

    Upon entering the context manager, `fetch_credentials` is called to fetch
    credentials, and a background thread is started for automatically refreshing
    credentials.  The background thread will use `fetch_credentials` to fetch
    new credentials `buffer_seconds` seconds _prior_ to expiration of the most
    recently fetched credentials. Upon exit, the background thread is notified
    to stop refreshing credentials.

    The value returned upon entering the context manager is a multiprocessing
    value proxy, and the proxy's ``value`` attribute is the current set of
    credentials.  The background thread updates the attribute value each time
    it fetches new credentials.  The proxy can be shared across processes, and
    reads and writes to the proxy value are atomic, but processes should only
    read the attribute, as the credentials refreshing thread is responsible for
    updating the attribute value.

    Parameters
    ----------
    ctx
        Multiprocessing context to use for creating a proxy value for sharing
        AWS S3 credentials across processes.  This must be the same context
        used for creating a process pool with processes that want to read
        the value of the yielded proxy value.
    fetch_credentials
        Callable that fetches AWS S3 temporary credentials.
    buffer_seconds
        Number of seconds _prior_ to the expiration of the most recently
        fetched credentials that new credentials should be fetched.
    utc_now
        Callable that returns a datetime value representing the "current" time
        in the UTC timezone.  Intended to aid testing, not for end-users.

    Yields
    ------
    credentials_proxy: multiprocessing.managers.ValueProxy
        Value proxy with a ``value`` attribute set AWS S3 tempoary credentials,
        which is a dictionary containing the keys "accessKeyId",
        "secretAccessKey", "sessionToken", and "expiration".  All values are
        of type string, and the value of "expiration" can be passed to
        `datetime.datetime.fromisoformat` to construct a datetime value.

    Examples
    --------
    >>> import multiprocessing as mp
    >>> import time
    >>> from datetime import datetime, timedelta, UTC

    >>> utc_nows = (
    ...     datetime.fromisoformat("2026-04-09 12:00:00+00:00"),
    ...     datetime.fromisoformat("2026-04-09 12:00:01+00:00"),
    ...     datetime.fromisoformat("2026-04-09 12:00:02+00:00"),
    ... )

    >>> clock1 = iter(utc_nows)
    >>> clock2 = iter(utc_nows)

    >>> def utc_now() -> datetime:
    ...     return next(clock1)

    >>> def fetch_creds():
    ...     expiration = (next(clock2) + timedelta(seconds=1)).isoformat()
    ...     return {"expiration": expiration}

    Upon creating the credentials proxy, credentials are fetched immediately,
    and the proxy value is set to the fetched credentials:

    >>> with credentials_proxy(
    ...     mp.get_context("spawn"),
    ...     fetch_creds,
    ...     buffer_seconds=0,  # Should be unnecessary outside of testing
    ...     utc_now=utc_now,  # Should be unnecessary outside of testing
    ... ) as proxy:
    ...     print(proxy.value)  # Obtain initial creds
    ...     time.sleep(1.1)  # Do some work long enough for creds to expire
    ...     print(proxy.value)  # We should now have fresh creds
    {'expiration': '2026-04-09T12:00:01+00:00'}
    {'expiration': '2026-04-09T12:00:02+00:00'}

    When the context manager exits, the credentials refresher is cancelled.
    Subsequently, the value of the credentials proxy will always return the
    last credentials fetched before the context manager was exited:

    >>> time.sleep(1.1)
    >>> proxy.value
    {'expiration': '2026-04-09T12:00:02+00:00'}
    """

    def trace_fetch_credentials() -> "AWSCredentials":
        creds = fetch_credentials()
        log_credentials_expiration(creds)
        return creds

    creds_proxy = ctx.Manager().Value(object, trace_fetch_credentials())
    # We need an event in order to be able to signal to the thread that it
    # should stop refreshing credentials.
    cancelled = threading.Event()

    threading.Thread(
        target=keep_credentials_fresh,
        args=(trace_fetch_credentials, creds_proxy),
        kwargs={
            "cancelled": cancelled,
            "utc_now": utc_now,
            "buffer_seconds": buffer_seconds,
        },
        daemon=True,
    ).start()

    try:
        yield creds_proxy
    finally:
        # Signal that we don't want credentials refreshed any longer.
        cancelled.set()


def keep_credentials_fresh(
    fetch_credentials: Callable[[], AWSCredentials],
    credentials_proxy: ValueProxy["AWSCredentials"],
    *,
    buffer_seconds: float = 5 * 60,  # 5 minutes
    cancelled: threading.Event,
    utc_now: Callable[[], datetime],
) -> None:
    """Keep AWS temporary credentials fresh.

    This function is intended to be the target of a thread, so that it can
    refresh credentials in the background.

    Assumes `credentials_proxy`'s `value` attribute was set to a set of
    credentials beforehand (ideally fresh, but not necessarily).  Repeatedly
    sleeps until `buffer_seconds` seconds _prior_ to expiration of the current
    set of credentials, then calls `fetch_credentials` and updates
    `credentials_proxy`'s `value` attribute with the fetched credentials, until
    the `cancelled` event is set.

    Parameters
    ----------
    fetch_credentials
        Callable that returns a fresh set of AWS temporary credentials.
    credentials_proxy
        Value proxy with a `value` attribute set to a fresh set of credentials.
    buffer_seconds
        Number of seconds _prior_ to the expiration of the credentials
        referenced by `credentials_proxy` to call `fetch_credentials` to fetch
        fresh credentials and update the proxy value.
    cancelled
        Threading event checked prior to each call to `fetch_credentials`.
        If the event is set, the refresh loop exits, and credentials are no
        longer refreshed.
    utc_now
        For testing purposes only.
    """
    while True:
        ttl_seconds = seconds_remaining(credentials_proxy.value, utc_now=utc_now)
        sleep_seconds = max(0.5, ttl_seconds - buffer_seconds)
        logger.info("AWS credentials refresher sleeping for %ss", round(sleep_seconds))
        time.sleep(sleep_seconds)

        if cancelled.is_set():
            logger.info("Cancelled AWS credentials refresher")
            break

        try:
            credentials_proxy.value = fetch_credentials()
        except Exception as e:
            logger.error("Failed to fetch AWS credentials: %s.  Retrying...", e)


def seconds_remaining(
    creds: AWSCredentials,
    *,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> float:
    """Calculate time-to-live in seconds for a set of temporary AWS credentials.

    Parameters
    ----------
    creds
        Set of AWS temporary credentials with an "expiration" key associated
        with a string value that is valid for converting to a datetime value
        via the `datetime.datetime.fromisformat` function.
    utc_now
        Callable that returns the "current" time in the UTC timezone.  Intended
        only for testing.

    Returns
    -------
    int
        Number of seconds until the credentials expire.  If the credentials
        have already expired, this will be a negative number.

    Examples
    --------
    >>> from datetime import datetime, timedelta

    For expiration dates in the future, `seconds_remaining` returns a positive
    value indicating how many seconds in the future the credentials will expire:

    >>> expiration = "2026-04-09 17:24:06+00:00"
    >>> creds = {"expiration": expiration}
    >>> utc_now = lambda: datetime.fromisoformat(expiration) - timedelta(seconds=4)
    >>> seconds_remaining(creds, utc_now=utc_now)
    4.0

    For credentials that have already expired, `seconds_remaining` returns a
    negative value, indicating how many seconds have passed since they expired:

    >>> utc_now = lambda: datetime.fromisoformat(expiration) + timedelta(seconds=4)
    >>> seconds_remaining(creds, utc_now=utc_now)
    -4.0
    """
    expiration = datetime.fromisoformat(creds["expiration"])
    remaining = (expiration - utc_now()).total_seconds()

    logger.info("AWS credentials expire in %ss", round(remaining))

    return remaining
