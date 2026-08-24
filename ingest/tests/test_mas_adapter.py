"""MAS adapter tests against a real (trimmed) landing page captured 2026-08-25.

The fixture is genuine MAS HTML — synthetic markup would hide exactly the quirks we
need to survive (three different /-/media/ path eras, sc_lang/hash query strings).
"""
from pathlib import Path

from crawler.mas import MasAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "mas_notice_626_landing.html"


def _discover():
    html = FIXTURE.read_text(encoding="utf-8")
    return MasAdapter().discover(html, "Notice 626")


def test_discovers_full_version_history():
    refs = _discover()
    # The live page carried 16 PDF anchors; several are duplicate links to the same
    # document, so distinct documents are fewer. What matters: we find many versions,
    # not just the current one.
    assert len(refs) >= 10


def test_urls_are_absolute_and_query_stripped():
    for r in _discover():
        assert r.url.startswith("https://www.mas.gov.sg/")
        assert "?" not in r.url  # sc_lang / hash dropped so dedup keys on the document


def test_spans_multiple_publishing_eras():
    urls = " ".join(r.url for r in _discover())
    # Three distinct path eras seen for this one instrument — proves we must not
    # template URLs (see mas.py docstring).
    assert "/-/media/amld-amendments" in urls
    assert "/-/media/mas-media-library/" in urls
    assert "/-/media/mas/" in urls


def test_finds_known_historical_versions():
    urls = {r.url for r in _discover()}
    expected = {
        "https://www.mas.gov.sg/-/media/amld-amendments---30-june-2025/mas-notice-626.pdf",
        (
            "https://www.mas.gov.sg/-/media/mas-media-library/regulation/notices/amld/"
            "notice-626/mas-notice-626-dated-28-march-2024.pdf"
        ),
    }
    assert expected <= urls


def test_no_duplicate_urls():
    refs = _discover()
    assert len({r.url for r in refs}) == len(refs)
