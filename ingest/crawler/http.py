"""Polite HTTP client for regulator sites.

Every request goes through a RateLimiter the client owns, so politeness cannot be
bypassed by a caller. Supports conditional requests (ETag / Last-Modified) so we do
not re-download unchanged documents (brief §4.4).

User-Agent note (verified 2026-08-25): MAS sits behind a WAF that answers HTTP 200
with a "Maintenance" HTML page when the UA does not begin with "Mozilla/5.0". A bare
descriptive bot UA is silently served junk. The UA below keeps the brief's requirement
to identify ourselves and give a contact address, while using the "Mozilla/5.0
(compatible; ...)" form the WAF accepts. We do not impersonate a real browser, and
robots.txt permits all paths with Crawl-delay: 2, which we honour.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Self

import httpx

from .ratelimit import RateLimiter

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; mas-delta-engine/0.1; "
    "+https://github.com/jewlurk/mas-delta-engine; contact: hs20.26@ichat.sp.edu.sg)"
)

# WAF block detector: the maintenance page is served with HTTP 200, so status alone
# is not enough to trust a response.
_BLOCK_MARKERS = ("<title>Maintenance</title>", "this service is currently unavailable")


class BlockedError(RuntimeError):
    """The host served a block/maintenance page instead of real content."""


@dataclass
class Fetched:
    url: str
    status: int
    content: bytes
    content_type: str
    etag: str | None
    last_modified: str | None

    @property
    def not_modified(self) -> bool:
        return self.status == 304


class PoliteClient:
    def __init__(
        self,
        min_interval_seconds: float = 2.0,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.limiter = RateLimiter(min_interval_seconds)
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )

    def fetch(
        self, url: str, etag: str | None = None, last_modified: str | None = None
    ) -> Fetched:
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        self.limiter.acquire()
        r = self._client.get(url, headers=headers)

        content_type = r.headers.get("content-type", "")
        if r.status_code == 200 and content_type.startswith("text/html"):
            head = r.content[:4000].decode("utf-8", "ignore").lower()
            if any(m.lower() in head for m in _BLOCK_MARKERS):
                raise BlockedError(f"host served a block/maintenance page for {url}")

        return Fetched(
            url=str(r.url),
            status=r.status_code,
            content=r.content,
            content_type=content_type,
            etag=r.headers.get("etag"),
            last_modified=r.headers.get("last-modified"),
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
