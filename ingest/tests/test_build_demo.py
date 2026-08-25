"""The public changelog pages.

These exist because of one bug: the delta query's columns were consumed positionally,
render_instrument sliced the wrong two, and `sections.body` ended up in the slot the
renderer treated as `ai_summary`. Every change without a real summary was published
with the clause's full text as its summary line — up to 1,764 words of MAS's own
wording on a public page, which §11 forbids outright. It shipped and nobody noticed.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from build_demo import (
    DELTA_COLUMNS,
    EXCERPT_CAP,
    col,
    render_instrument,
    render_recent,
    revision_headline,
)

CLAUSE_BODY = "For the purposes of this Notice " + "the full clause text " * 200
SUMMARY = "Screening threshold changed from SGD 20,000 to SGD 5,000."


def row(**over):
    base = {
        "instrument_id": 1, "from_version_id": 10, "to_version_id": 11,
        "from_date": date(2024, 3, 28), "to_date": date(2025, 6, 30),
        "effective_date": date(2025, 7, 1),
        "op": "MODIFIED", "new_key": "6.14", "old_key": "6.14", "severity": 4,
        "diff_html": "<del>old</del> <ins>new</ins>", "similarity": 0.9,
        "external_ref": "Notice 626",
        "source_url": "https://www.mas.gov.sg/regulation/notices/notice-626",
        "new_body": CLAUSE_BODY, "ai_summary": SUMMARY, "obligation_change": True,
    }
    base.update(over)
    return tuple(base[name] for name in DELTA_COLUMNS)


INSTRUMENT = (1, "Notice 626", "AML/CFT - Banks",
              "https://www.mas.gov.sg/regulation/notices/notice-626", ["bank"])


def test_column_map_matches_the_query():
    assert col(row(), "ai_summary") == SUMMARY
    assert col(row(), "new_body") == CLAUSE_BODY
    assert col(row(), "op") == "MODIFIED"
    assert col(row(), "obligation_change") is True


def test_instrument_page_shows_the_summary_not_the_clause():
    html, _total, _latest = render_instrument(INSTRUMENT, [row()], {11: 100})
    assert SUMMARY in html
    assert "the full clause text the full clause text" not in html


def test_instrument_page_never_publishes_the_clause_when_there_is_no_summary():
    """The regression that shipped: no summary must not mean 'print the whole clause'."""
    html, _total, _latest = render_instrument(
        INSTRUMENT, [row(ai_summary=None)], {11: 100})
    assert "the full clause text the full clause text" not in html
    assert "No summary generated" in html


def test_front_page_shows_the_summary_not_the_clause():
    html = render_recent([row()])
    assert SUMMARY in html
    assert "the full clause text the full clause text" not in html


def test_obligation_count_counts_obligations_not_clauses():
    rows = [row(new_key="6.14", obligation_change=True),
            row(new_key="6.15", obligation_change=False),
            row(new_key="6.16", obligation_change=False)]
    assert "1 change affecting an obligation" in revision_headline(rows)


def test_operation_counts_are_read_from_the_op_column():
    rows = [row(new_key="1.1", op="ADDED"), row(new_key="1.2", op="ADDED"),
            row(new_key="1.3", op="MODIFIED"), row(new_key="1.4", op="REMOVED")]
    line = revision_headline(rows)
    assert "2 new clauses" in line and "1 amended" in line and "1 removed" in line


def test_excerpt_cap_limits_how_many_clauses_a_revision_shows():
    """§11: never more than 40% of an instrument's clauses in one comparison."""
    rows = [row(new_key=f"6.{n}") for n in range(50)]
    html, _total, _latest = render_instrument(INSTRUMENT, rows, {11: 20})
    shown = html.count('<article class="delta')
    assert shown == int(20 * EXCERPT_CAP)
    assert "further changes in this revision are not shown" in html


def test_every_front_page_entry_links_to_mas():
    html = render_recent([row()])
    assert 'href="https://www.mas.gov.sg/regulation/notices/notice-626"' in html
