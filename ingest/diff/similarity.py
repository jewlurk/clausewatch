"""Trigram similarity, matching PostgreSQL pg_trgm semantics.

Two implementations of the same measure exist deliberately:

  * this module — used for offline validation and tests, so the differ can be tuned
    against real documents without a database.
  * SQL `similarity()` over the `sections_body_trgm_idx` GIN index — used in
    production (T16), because scanning every section in Python does not scale.

They must agree, or a threshold tuned offline is meaningless in production. pg_trgm
lowercases, splits on non-alphanumerics, pads each word with two leading spaces and
one trailing space, and scores |A n B| / |A u B| over the resulting trigram sets.
"""
from __future__ import annotations

import re

_WORD_SPLIT = re.compile(r"[^a-zA-Z0-9]+")


def trigrams(text: str) -> set[str]:
    """pg_trgm-compatible trigram set."""
    out: set[str] = set()
    for word in _WORD_SPLIT.split(text.lower()):
        if not word:
            continue
        padded = f"  {word} "
        for i in range(len(padded) - 2):
            out.add(padded[i : i + 3])
    return out


def similarity(a: str, b: str) -> float:
    """Jaccard similarity over trigram sets. Matches pg_trgm's similarity()."""
    ta, tb = trigrams(a), trigrams(b)
    if not ta and not tb:
        return 1.0
    union = ta | tb
    if not union:
        return 0.0
    return len(ta & tb) / len(union)
