"""Severity scoring — deterministic and free. Brief §10.

The LLM only ever sees severity >= 3, so this function controls the entire AI budget.
"""
from __future__ import annotations

import re

from parse.normalise import normalise

MODALS = ("shall", "must", "is required to", "may not", "shall not", "prohibited")

_NUMBER_RE = re.compile(r"\b[\d,]+(?:\.\d+)?%?\b")
_DATE_RE = re.compile(r"\b\d{1,2}\s+\w+\s+20\d\d\b")


def _numbers(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text or ""))


_PUNCT_RE = re.compile(r"[^a-z0-9]+")


def _words_only(text: str) -> str:
    """Letters and digits only — used to spot changes that carry no meaning."""
    return _PUNCT_RE.sub(" ", normalise(text).lower()).strip()


def score_severity(old_body: str | None, new_body: str) -> int:
    """1 cosmetic .. 5 new obligation."""
    if old_body and normalise(old_body).lower() == normalise(new_body).lower():
        return 1

    # Punctuation-only edits ("...of 6:" -> "...of 6 -") are reformatting, not
    # regulatory change. Measured: these were a false positive on the 2024->2025 pair.
    if old_body and _words_only(old_body) == _words_only(new_body):
        return 1

    # Same words, different order. In a legal instrument a genuine amendment changes
    # words; an identical multiset in a different order is a PDF reading-order artifact
    # at a line break. Verified case: Notice 626 para 8.1, where the 2024 extraction
    # yields "party international officials, members of organisations" for the same
    # source text MAS left untouched. Judgement call — see docs/threshold-tuning.md.
    if old_body and sorted(_words_only(old_body).split()) == sorted(
        _words_only(new_body).split()
    ):
        return 1

    severity = 3
    lowered_new = new_body.lower()
    lowered_old = (old_body or "").lower()

    added_modal = any(m in lowered_new and m not in lowered_old for m in MODALS)
    numbers_changed = _numbers(old_body) != _numbers(new_body)
    dates_changed = bool(_DATE_RE.search(new_body))

    if numbers_changed:
        severity += 1
    if added_modal:
        severity += 1
    if dates_changed:
        severity = max(severity, 4)
    return min(severity, 5)
