"""Shared, enforced rate limiter.

Brief §4.4 requires <=1 request per 2 seconds against a regulator, enforced as a
primitive rather than scattered sleep() calls. The limiter is owned by the HTTP
client, so no caller can issue a request that bypasses it.

One limiter instance per host. Thread-safe: acquire() serialises callers and returns
only when the caller is allowed to proceed.
"""
from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, min_interval_seconds: float) -> None:
        if min_interval_seconds <= 0:
            raise ValueError("min_interval_seconds must be > 0")
        self.min_interval = min_interval_seconds
        self._lock = threading.Lock()
        self._last_release: float | None = None

    def acquire(self, _sleep=time.sleep, _now=time.monotonic) -> float:
        """Block until the caller may make a request. Returns seconds waited."""
        with self._lock:
            now = _now()
            if self._last_release is None:
                self._last_release = now
                return 0.0
            earliest = self._last_release + self.min_interval
            wait = earliest - now
            if wait > 0:
                _sleep(wait)
                self._last_release = earliest
                return wait
            self._last_release = now
            return 0.0
