"""SqlMatcher (T16).

The real proof that the SQL matcher matches the in-memory one is scripts/verify_matcher.py,
which needs a live pg_trgm database and runs in CI. What is unit-testable offline is the
one path that must never touch the database: an empty candidate set short-circuits to
None before any query, so a fully-matched pair costs no SQL.
"""
from __future__ import annotations

from matcher import SqlMatcher


class ExplodingConn:
    def cursor(self):  # pragma: no cover - must never be called
        raise AssertionError("SqlMatcher queried the database with no candidates")


def test_no_candidates_returns_none_without_querying():
    matcher = SqlMatcher(ExplodingConn(), version_id=1)
    assert matcher.best_match("some clause body", {}) is None


def test_it_presents_the_matcher_interface():
    """Structural parity with InMemoryMatcher — same method the differ calls."""
    m = SqlMatcher(ExplodingConn(), 1)
    assert callable(m.best_match)
