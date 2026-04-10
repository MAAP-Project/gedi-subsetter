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
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
    buffer_seconds: float = 5 * 60,  # 5 minutes
) -> Generator[ValueProxy["AWSCredentials"]]:
    """
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
    ...     time.sleep(1.1)  # Do some work
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
        cancelled.set()


def keep_credentials_fresh(
    fetch_credentials: Callable[[], AWSCredentials],
    credentials_proxy: ValueProxy["AWSCredentials"],
    *,
    cancelled: threading.Event,
    utc_now: Callable[[], datetime],
    buffer_seconds: float = 5 * 60,  # 5 minutes
) -> None:
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
            logger.error("Failed to fetch AWS credentials: %s", e, exc_info=True)


def seconds_remaining(
    creds: AWSCredentials,
    *,
    utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> float:
    """
    Examples
    --------
    >>> from datetime import datetime, timedelta

    >>> expiration = "2026-04-09 17:24:06+00:00"
    >>> creds = {"expiration": expiration}
    >>> utc_now = lambda: datetime.fromisoformat(expiration) - timedelta(seconds=4)
    >>> seconds_remaining(creds, utc_now=utc_now)
    4.0
    """
    expiration = datetime.fromisoformat(creds["expiration"])
    remaining = (expiration - utc_now()).total_seconds()

    logger.info("AWS credentials expire in %ss", round(remaining))

    return remaining
