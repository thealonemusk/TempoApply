"""
Shared HTTP client with exponential backoff.

Every scraper here talks to a third-party endpoint that rate-limits. Without a
retry layer a 429 arrives as an ordinary response whose body parses to zero
results, and callers read that as "no more jobs" — the scan truncates silently
and nothing in the logs says why.

`get`/`post` are drop-in replacements for `requests.get`/`requests.post`: they
return the final Response (so existing `status_code != 200` checks keep
working) and only raise when every attempt raised, exactly as requests does
today. What they add is retrying the statuses that mean "ask again later".
"""
from __future__ import annotations

import random
import threading
import time
from typing import Optional

import requests
from loguru import logger

DEFAULT_TIMEOUT = 15
MAX_RETRIES = 4
BASE_DELAY_SEC = 0.5
MAX_DELAY_SEC = 8.0
MAX_RETRY_AFTER_SEC = 30.0

# Statuses that mean "transient — ask again", as opposed to 403/404 which mean
# "this answer will not change on a retry".
RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}

# Scrapers fan out over thread pools, and a requests.Session is not documented
# as thread-safe. One session per thread keeps connection pooling (which
# matters at a dozen workers x hundreds of requests) without sharing state.
_local = threading.local()


def _session() -> requests.Session:
    session = getattr(_local, "session", None)
    if session is None:
        session = requests.Session()
        _local.session = session
    return session


def _retry_after_seconds(response: requests.Response) -> Optional[float]:
    """Honour Retry-After when the server sends a plain number of seconds.

    The HTTP-date form is ignored rather than parsed: it is rare on these
    endpoints, and a misparsed date could stall a scan for hours.
    """
    raw = response.headers.get("Retry-After", "").strip()
    if not raw.isdigit():
        return None
    return min(float(raw), MAX_RETRY_AFTER_SEC)


def _backoff_delay(attempt: int, response: Optional[requests.Response]) -> float:
    if response is not None:
        explicit = _retry_after_seconds(response)
        if explicit is not None:
            return explicit
    delay = min(BASE_DELAY_SEC * (2 ** attempt), MAX_DELAY_SEC)
    return delay + random.uniform(0, 0.5)


def request(
    method: str,
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    **kwargs,
) -> requests.Response:
    """Issue a request, retrying transient failures with exponential backoff.

    Returns the last Response received. Raises requests.RequestException only
    if every attempt raised without producing a response.
    """
    last_exc: Optional[Exception] = None
    last_response: Optional[requests.Response] = None

    for attempt in range(max_retries + 1):
        try:
            response = _session().request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            time.sleep(_backoff_delay(attempt, None))
            continue

        last_response = response
        last_exc = None
        if response.status_code not in RETRYABLE_STATUSES:
            return response
        if attempt == max_retries:
            logger.warning(
                f"HTTP {response.status_code} after {max_retries + 1} attempts: {url}"
            )
            return response

        delay = _backoff_delay(attempt, response)
        logger.debug(
            f"HTTP {response.status_code} on {url} — retry "
            f"{attempt + 1}/{max_retries} in {delay:.1f}s"
        )
        time.sleep(delay)

    if last_response is not None:
        return last_response
    raise last_exc if last_exc else requests.RequestException(f"Request failed: {url}")


def get(url: str, **kwargs) -> requests.Response:
    return request("GET", url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    return request("POST", url, **kwargs)


def is_rate_limited(response: requests.Response) -> bool:
    """True when a response is a rate-limit/outage that survived every retry."""
    return response.status_code in RETRYABLE_STATUSES
