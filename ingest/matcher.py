"""SQL trigram matcher (T16, brief §9/§16).

The brief is explicit: `trgm_best_match` must be a SQL query using the GIN index, not
all sections loaded into Python and looped. `diff/delta.py` keeps a pure InMemoryMatcher
for tests and threshold tuning (no database); production uses this one, which pushes the
renumber-hunt into Postgres against `sections_body_trgm_idx`.

Both must use the same similarity measure — pg_trgm's `similarity()` and the in-memory
Jaccard-over-trigrams are meant to be identical, and `scripts/verify_matcher.py` proves
it by running the whole corpus differ through both and asserting the deltas match before
this is trusted in the pipeline. The GIN index accelerates the `<->` distance ordering;
`similarity()` returns the score the differ compares against RENUMBER_THRESHOLD.

Kept out of `diff/` on purpose: the differ has no database dependency, and adding one to
satisfy a single production matcher would be the wrong trade. This module has the psycopg
dependency; the differ stays pure and testable offline.
"""
from __future__ import annotations

import psycopg


class SqlMatcher:
    """Finds the best-matching section in one version via the pg_trgm GIN index.

    Bound to a target version_id. `best_match(body, candidates)` searches only the
    candidate keys — the differ passes the new-version sections not yet claimed — and
    returns (section_key, similarity) for the closest, or None when there are no
    candidates. The candidate bodies themselves are ignored: they are already in the
    database, and re-sending them would be the Python loop this exists to remove.
    """

    def __init__(self, conn: psycopg.Connection, version_id: int) -> None:
        self.conn = conn
        self.version_id = version_id

    def best_match(self, body: str, candidates) -> tuple[str, float] | None:
        keys = list(candidates)
        if not keys:
            return None
        with self.conn.cursor() as cur:
            cur.execute(
                """
                select section_key, similarity(body, %(body)s) as sim
                  from sections
                 where version_id = %(vid)s
                   and section_key = any(%(keys)s)
                 order by body <-> %(body)s
                 limit 1
                """,
                {"body": body, "vid": self.version_id, "keys": keys},
            )
            row = cur.fetchone()
        return (row[0], float(row[1])) if row else None
