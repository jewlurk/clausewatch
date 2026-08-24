"""Ingest pipeline: fetch -> hash -> dedup -> store -> record.

The dedup rule is the point of this module. MAS reissues the same PDF at the same URL
routinely, and the daily cron refetches every document it knows about. Without a
content check, every run would create a new version row and the differ would compute
deltas between byte-identical documents — producing a stream of empty changes that
would destroy trust faster than missing a change.

So: identical bytes never create a new version. The check is on the SHA-256 of the
response body, not on the URL, ETag, or fetch date. MAS does not send an ETag on its
landing pages (verified 2026-08-25), so content hashing is the only reliable signal.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from crawler.http import Fetched, PoliteClient
from store import ObjectStore, content_sha256, object_key

MIME_SUFFIX = {
    "application/pdf": ".pdf",
    "text/html": ".html",
}


class Outcome(str, Enum):
    CREATED = "created"  # new content, stored and recorded
    UNCHANGED = "unchanged"  # bytes already known, nothing written
    NOT_MODIFIED = "not_modified"  # server answered 304, nothing fetched


@dataclass
class IngestResult:
    outcome: Outcome
    url: str
    sha256: str | None = None
    r2_key: str | None = None
    version_id: int | None = None

    @property
    def is_new(self) -> bool:
        return self.outcome is Outcome.CREATED


class VersionRepository(Protocol):
    """Persistence for instrument_versions.

    A protocol so tests can use an in-memory double; the Postgres implementation
    lands once database credentials exist.
    """

    def version_exists(self, instrument_id: int, content_sha256: str) -> bool: ...

    def insert_version(
        self, *, instrument_id: int, content_sha256: str, r2_key: str, mime_type: str
    ) -> int: ...


def suffix_for(content_type: str) -> str:
    base = content_type.split(";")[0].strip().lower()
    return MIME_SUFFIX.get(base, ".bin")


def ingest_document(
    *,
    client: PoliteClient,
    store: ObjectStore,
    repository,
    regulator_code: str,
    instrument_id: int,
    instrument_ref: str,
    url: str,
    etag: str | None = None,
    last_modified: str | None = None,
) -> IngestResult:
    """Fetch one document and record it if its content is new."""
    fetched: Fetched = client.fetch(url, etag=etag, last_modified=last_modified)

    if fetched.not_modified:
        # Server confirmed nothing changed; we never even received a body.
        return IngestResult(outcome=Outcome.NOT_MODIFIED, url=url)

    sha = content_sha256(fetched.content)

    if repository.version_exists(instrument_id, sha):
        return IngestResult(outcome=Outcome.UNCHANGED, url=url, sha256=sha)

    content_type = fetched.content_type.split(";")[0].strip() or "application/octet-stream"
    key = object_key(regulator_code, instrument_ref, sha, suffix_for(content_type))

    # Store before recording. A stored object with no row is harmless and will be
    # overwritten on the next run; a row pointing at a missing object is not.
    if not store.exists(key):
        store.put(key, fetched.content, content_type)

    version_id = repository.insert_version(
        instrument_id=instrument_id,
        content_sha256=sha,
        r2_key=key,
        mime_type=content_type,
    )

    return IngestResult(
        outcome=Outcome.CREATED, url=url, sha256=sha, r2_key=key, version_id=version_id
    )
