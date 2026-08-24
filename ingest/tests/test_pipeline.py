"""Ingest pipeline tests.

The dedup guarantee gets the most coverage: the daily cron refetches every known
document, so if identical bytes created a new version, the differ would emit empty
changes on every run.
"""
import httpx
import pytest

from crawler.http import PoliteClient
from pipeline import Outcome, ingest_document, suffix_for
from store import LocalStore, content_sha256, object_key

PDF_BYTES = b"%PDF-1.7\nfake notice body\n"
OTHER_PDF = b"%PDF-1.7\nrevised notice body\n"


class FakeRepository:
    """In-memory stand-in for instrument_versions."""

    def __init__(self):
        self.rows: list[dict] = []

    def version_exists(self, instrument_id: int, content_sha256: str) -> bool:
        return any(
            r["instrument_id"] == instrument_id and r["content_sha256"] == content_sha256
            for r in self.rows
        )

    def insert_version(self, *, instrument_id, content_sha256, r2_key, mime_type) -> int:
        self.rows.append(
            {
                "instrument_id": instrument_id,
                "content_sha256": content_sha256,
                "r2_key": r2_key,
                "mime_type": mime_type,
            }
        )
        return len(self.rows)


def make_client(handler) -> PoliteClient:
    # min_interval kept tiny: politeness is covered by the rate limiter's own tests,
    # and no real host is contacted here.
    return PoliteClient(
        min_interval_seconds=0.001, transport=httpx.MockTransport(handler)
    )


def pdf_handler(body=PDF_BYTES, status=200, headers=None):
    def handler(request):
        return httpx.Response(
            status,
            content=body,
            headers={"content-type": "application/pdf", **(headers or {})},
        )

    return handler


def run(client, store, repo, url="https://www.mas.gov.sg/x.pdf"):
    return ingest_document(
        client=client,
        store=store,
        repository=repo,
        regulator_code="MAS",
        instrument_id=1,
        instrument_ref="Notice 626",
        url=url,
    )


# ---------- helpers ----------


def test_object_key_is_content_addressed():
    key = object_key("MAS", "Notice 626", "abc123", ".pdf")
    assert key == "MAS/Notice_626/abc123.pdf"


def test_object_key_is_filesystem_safe():
    assert "/" not in object_key("MAS", "SFA04/N02", "d", ".pdf").split("/", 1)[1].split("/")[0]


def test_suffix_from_content_type():
    assert suffix_for("application/pdf") == ".pdf"
    assert suffix_for("text/html; charset=utf-8") == ".html"
    assert suffix_for("application/octet-stream") == ".bin"


# ---------- first ingest ----------


def test_new_document_is_stored_and_recorded(tmp_path):
    store, repo = LocalStore(tmp_path), FakeRepository()
    result = run(make_client(pdf_handler()), store, repo)

    assert result.outcome is Outcome.CREATED
    assert result.is_new
    assert result.sha256 == content_sha256(PDF_BYTES)
    assert store.exists(result.r2_key)
    assert len(repo.rows) == 1
    assert repo.rows[0]["mime_type"] == "application/pdf"


def test_stored_bytes_match_what_was_fetched(tmp_path):
    store, repo = LocalStore(tmp_path), FakeRepository()
    result = run(make_client(pdf_handler()), store, repo)
    assert (tmp_path / result.r2_key).read_bytes() == PDF_BYTES


# ---------- the dedup guarantee ----------


def test_identical_bytes_never_create_a_second_version(tmp_path):
    """Brief T12: identical bytes must not create a new version."""
    store, repo = LocalStore(tmp_path), FakeRepository()
    client = make_client(pdf_handler())

    first = run(client, store, repo)
    second = run(client, store, repo)

    assert first.outcome is Outcome.CREATED
    assert second.outcome is Outcome.UNCHANGED
    assert not second.is_new
    assert len(repo.rows) == 1


def test_repeated_daily_runs_stay_at_one_version(tmp_path):
    store, repo = LocalStore(tmp_path), FakeRepository()
    client = make_client(pdf_handler())
    outcomes = [run(client, store, repo).outcome for _ in range(5)]

    assert outcomes[0] is Outcome.CREATED
    assert all(o is Outcome.UNCHANGED for o in outcomes[1:])
    assert len(repo.rows) == 1


def test_changed_bytes_do_create_a_new_version(tmp_path):
    store, repo = LocalStore(tmp_path), FakeRepository()

    first = run(make_client(pdf_handler(PDF_BYTES)), store, repo)
    second = run(make_client(pdf_handler(OTHER_PDF)), store, repo)

    assert first.outcome is Outcome.CREATED
    assert second.outcome is Outcome.CREATED
    assert len(repo.rows) == 2
    assert first.sha256 != second.sha256
    assert first.r2_key != second.r2_key


def test_same_content_at_a_different_url_is_still_deduped(tmp_path):
    # MAS republishes identical documents under new /-/media/ paths across eras.
    store, repo = LocalStore(tmp_path), FakeRepository()
    client = make_client(pdf_handler())

    run(client, store, repo, url="https://www.mas.gov.sg/-/media/old/x.pdf")
    second = run(client, store, repo, url="https://www.mas.gov.sg/-/media/new/x.pdf")

    assert second.outcome is Outcome.UNCHANGED
    assert len(repo.rows) == 1


# ---------- conditional requests and failures ----------


def test_not_modified_response_writes_nothing(tmp_path):
    store, repo = LocalStore(tmp_path), FakeRepository()

    def handler(request):
        return httpx.Response(304, headers={"content-type": "application/pdf"})

    result = ingest_document(
        client=make_client(handler),
        store=store,
        repository=repo,
        regulator_code="MAS",
        instrument_id=1,
        instrument_ref="Notice 626",
        url="https://www.mas.gov.sg/x.pdf",
        etag='"abc"',
    )

    assert result.outcome is Outcome.NOT_MODIFIED
    assert repo.rows == []


def test_waf_block_page_is_never_stored(tmp_path):
    """MAS answers HTTP 200 with a maintenance page for bare bot UAs. Storing that
    would poison the corpus with junk that parses to zero clauses."""
    from crawler.http import BlockedError

    store, repo = LocalStore(tmp_path), FakeRepository()

    def handler(request):
        return httpx.Response(
            200,
            content=b"<html><title>Maintenance</title></html>",
            headers={"content-type": "text/html"},
        )

    with pytest.raises(BlockedError):
        run(make_client(handler), store, repo)

    assert repo.rows == []
