"""HTTP client for TickTick's private web-app endpoints.

Only two calls, both read-only:
- ``GET /api/v3/batch/check/{checkpoint}``: the sync delta.
- ``GET /api/v2/project/all/completedInAll/``: closed tasks, paged backwards.

A 401 means the ``t`` cookie was rejected. It raises ``AuthRejected`` and is never
retried: retrying a dead cookie looks like a bot. Only network errors (connect,
read, timeout) are retried, at most ``retries`` times with exponential backoff.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import httpx

from .parse import completed_cursor

BASE_URL = "https://api.ticktick.com"


class AuthRejected(Exception):
    """TickTick answered 401: the ``t`` cookie is no longer accepted."""


@dataclass(frozen=True)
class TickTickConfig:
    cookie_t: str
    user_agent: str
    x_device: str
    timezone: str = "Asia/Ho_Chi_Minh"
    locale: str = "en_US"
    base_url: str = BASE_URL

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> TickTickConfig:
        env = dict(os.environ) if env is None else env
        names = ("TICKTICK_COOKIE_T", "TICKTICK_USER_AGENT", "TICKTICK_X_DEVICE")
        missing = [n for n in names if not env.get(n)]
        if missing:
            raise RuntimeError(f"missing environment variables: {', '.join(missing)}")
        return cls(
            cookie_t=env["TICKTICK_COOKIE_T"],
            user_agent=env["TICKTICK_USER_AGENT"],
            x_device=env["TICKTICK_X_DEVICE"],
            timezone=env.get("TICKTICK_TIMEZONE") or "Asia/Ho_Chi_Minh",
        )

    def __repr__(self) -> str:  # never leak the cookie into logs
        return f"TickTickConfig(cookie_t=<{len(self.cookie_t)} chars>, base_url={self.base_url!r})"

    def headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "X-Device": self.x_device,
            "x-tz": self.timezone,
            "hl": self.locale,
            "Cookie": f"t={self.cookie_t}",
            "Accept": "application/json, text/plain, */*",
        }


class TickTickClient:
    def __init__(
        self,
        config: TickTickConfig,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
        retries: int = 2,
        backoff_seconds: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.retries = retries
        self.backoff_seconds = backoff_seconds
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=config.base_url,
            headers=config.headers(),
            timeout=timeout,
            transport=transport,
        )

    def __enter__(self) -> TickTickClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        attempt = 0
        while True:
            try:
                response = self._http.get(path, params=params)
            except httpx.TransportError:
                if attempt >= self.retries:
                    raise
                self._sleep(self.backoff_seconds * (2**attempt))
                attempt += 1
                continue
            if response.status_code == 401:
                code = _error_code(response)
                raise AuthRejected(f"TickTick rejected the t cookie (401 {code})")
            response.raise_for_status()
            return response.json()

    def fetch_delta(self, checkpoint: int) -> dict[str, Any]:
        """One sync delta since ``checkpoint`` (ms timestamp; 0 = all open tasks)."""
        return self._get(f"/api/v3/batch/check/{int(checkpoint)}")

    def completed_page(self, to: str = "", limit: int = 1000) -> list[dict[str, Any]]:
        """One page of closed tasks (status 2 and -1), newest first, completed at or
        before ``to`` (``yyyy-MM-dd HH:mm:ss``; empty = now). The server caps a page
        at 100 rows whatever ``limit`` says."""
        params = {"from": "", "to": to, "limit": limit}
        return self._get("/api/v2/project/all/completedInAll/", params=params)

    def iter_completed(self, stop_at: str | None = None) -> Iterator[list[dict[str, Any]]]:
        """Page backwards from now, yielding only rows not seen on an earlier page.

        The cursor is the oldest ``completedTime`` on a page, inclusive, so each page
        repeats at least one row; rows are deduped on ``id``. Stops when a page adds
        nothing new (the floor) or once the cursor reaches ``stop_at`` (inclusive).
        """
        seen: set[str] = set()
        to = ""
        while True:
            page = self.completed_page(to)
            new = [row for row in page if row["id"] not in seen]
            if not new:
                return
            seen.update(row["id"] for row in new)
            yield new
            to = completed_cursor(page)
            if stop_at is not None and to <= stop_at:
                return


def _error_code(response: httpx.Response) -> str:
    try:
        return str(response.json().get("errorCode", ""))
    except ValueError:
        return ""
