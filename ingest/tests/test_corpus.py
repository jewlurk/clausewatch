"""Timeline construction and version classification (corpus.py).

The timeline decides which versions are compared and in what order. Two rules it must
never break: a version whose date could not be read is excluded rather than guessed
into the chain (an undated version placed arbitrarily produces a diff between versions
that may not really be adjacent), and tracked-changes copies never reach the timeline
at all (they carry old and new wording inline, so diffing them is nonsense).
"""
from __future__ import annotations

import logging
from datetime import date

from corpus import ParsedVersion, classify, deltas_across, timeline
from parse.sections import Section


def version(vid, r2_key, when, *, consolidated=True, tracked=False, sections=None):
    return ParsedVersion(
        version_id=vid,
        r2_key=r2_key,
        sections=sections or [],
        issue_date=when,
        effective_date=None,
        version_date=when,
        is_consolidated=consolidated,
        is_tracked=tracked,
    )


def sec(key, body):
    return Section(section_key=key, depth=1, ordinal=0, heading=None, body=body)


def test_timeline_orders_by_date():
    vs = [version(3, "c", date(2022, 3, 1)),
          version(1, "a", date(2015, 4, 24)),
          version(2, "b", date(2021, 6, 28))]
    assert [v.r2_key for v in timeline(vs)] == ["a", "b", "c"]


def test_undated_version_is_excluded_not_placed():
    vs = [version(1, "dated", date(2015, 4, 24)),
          version(2, "undated", None)]
    assert [v.r2_key for v in timeline(vs)] == ["dated"]


def test_the_dropped_version_is_named_in_the_log(caplog):
    """A future date-extraction regression must be diagnosable from the log alone."""
    vs = [version(1, "dated", date(2015, 4, 24)),
          version(2, "faan06-2002-cancelled.pdf", None)]
    with caplog.at_level(logging.WARNING):
        timeline(vs)
    assert "faan06-2002-cancelled.pdf" in caplog.text


def test_tracked_copies_never_reach_the_timeline():
    vs = [version(1, "clean", date(2021, 6, 28)),
          version(2, "tracked", date(2021, 6, 28), tracked=True)]
    assert [v.r2_key for v in timeline(vs)] == ["clean"]


def test_amendment_notices_are_not_consolidated():
    vs = [version(1, "consolidated", date(2021, 6, 28)),
          version(2, "amendment", date(2022, 3, 1), consolidated=False)]
    assert [v.r2_key for v in timeline(vs)] == ["consolidated"]


def test_deltas_across_compares_consecutive_pairs_only():
    old = version(1, "a", date(2021, 6, 28), sections=[sec("6.1", "the original text here")])
    new = version(2, "b", date(2022, 3, 1), sections=[sec("6.1", "the amended text here")])
    pairs = deltas_across([new, old])  # order-independent input
    assert len(pairs) == 1
    older, newer, _deltas = pairs[0]
    assert (older.r2_key, newer.r2_key) == ("a", "b")


def test_classify_reads_shape_and_the_tracked_marker():
    body = "\n".join(f"{n}.1 some clause body text" for n in range(1, 60))
    consolidated, tracked = classify(body, [sec(f"{n}.1", "x") for n in range(60)])
    assert consolidated and not tracked

    marker = "coloured and struck through represents deletion which will not appear"
    _, is_tracked = classify(marker + body, [sec(f"{n}.1", "x") for n in range(60)])
    assert is_tracked
