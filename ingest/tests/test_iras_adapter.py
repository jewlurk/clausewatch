"""IRAS adapter (T33) — the second regulator that proves the source abstraction holds.

The test that matters is not that IRAS works, but that adding it touched only an
adapter: it implements the same SourceAdapter protocol MasAdapter does, returns the
same DocumentRef type, and the parser/differ/schema are all untouched. It is exercised
against real captured IRAS markup (fixtures/iras_etax_listing.html), not a synthetic
sample, so the parsing is proven against the shape IRAS actually ships.
"""
from __future__ import annotations

from pathlib import Path

from crawler.base import DocumentRef, SourceAdapter
from crawler.iras import IrasAdapter
from crawler.mas import MasAdapter

FIXTURE = (Path(__file__).parent / "fixtures" / "iras_etax_listing.html").read_text()


def test_iras_adapter_satisfies_the_same_protocol_as_mas():
    """The whole point of T33: a regulator is a new adapter, nothing else."""
    assert isinstance(IrasAdapter(), SourceAdapter)
    assert isinstance(MasAdapter(), SourceAdapter)
    assert IrasAdapter().code == "IRAS"


def test_discovers_every_guide_on_the_listing():
    refs = IrasAdapter().discover(FIXTURE)
    titles = {r.instrument_ref for r in refs}
    assert titles == {
        "GST: Time of Supply Rules",
        "IRAS CARF e-Tax Guide (First Edition)",
        "GST: Major Exporter Scheme (MES)",
    }


def test_returns_the_shared_documentref_type():
    refs = IrasAdapter().discover(FIXTURE)
    assert all(isinstance(r, DocumentRef) for r in refs)


def test_the_size_hint_is_stripped_from_the_title():
    refs = IrasAdapter().discover(FIXTURE)
    assert all("(PDF," not in r.instrument_ref for r in refs)


def test_the_publication_date_is_carried_into_the_label():
    refs = {r.instrument_ref: r for r in IrasAdapter().discover(FIXTURE)}
    assert "18 Aug 2026" in refs["GST: Time of Supply Rules"].label


def test_the_cache_buster_is_dropped_and_the_modal_link_deduped():
    refs = IrasAdapter().discover(FIXTURE)
    # Three guides, three refs — the duplicate link inside each modal is not a fourth.
    assert len(refs) == 3
    for r in refs:
        assert "sfvrsn" not in r.url
        assert r.url.endswith(".pdf")


def test_an_empty_or_shell_page_yields_nothing_not_an_error():
    """The un-rendered IRAS shell has no article items — that is empty, not a crash."""
    assert IrasAdapter().discover("<html><body>Loading…</body></html>") == []
