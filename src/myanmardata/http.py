"""Minimal HTTP client for collectors (standard library only)."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Mapping

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


class FetchError(RuntimeError):
    """A source could not be fetched."""


def fetch(
    url: str,
    headers: Mapping[str, str] | None = None,
    timeout: float = 30.0,
    attempts: int = 3,
    backoff: float = 2.0,
) -> bytes:
    """GET ``url`` and return the body, retrying transient failures with exponential backoff."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https URLs
                return response.read()
        except urllib.error.HTTPError as exc:
            # 4xx other than 429 will not improve on retry.
            if 400 <= exc.code < 500 and exc.code != 429:
                raise FetchError(f"{url}: HTTP {exc.code}") from exc
            last = exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
        if attempt + 1 < attempts:
            time.sleep(backoff * 2**attempt)
    raise FetchError(f"{url}: {last}") from last
