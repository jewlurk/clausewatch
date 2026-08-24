"""Text normalisation applied before hashing and diffing.

Two versions of the same unchanged clause must produce byte-identical text, or the
differ reports phantom MODIFIED rows. MAS PDFs are justified, so word gaps come out as
runs of spaces that vary between reissues of identical text — that alone would break
sha256 equality. Non-breaking spaces and curly quotes vary the same way.
"""
from __future__ import annotations

import re
import unicodedata

# Page furniture. Verified against real fixtures: the running header is
# "[MAS Notice 626 (Amendment) 2025]" — the brief's narrower r'\[MAS Notice \d+\s*\]'
# does not match the amendment form, so it is widened here.
_FURNITURE = [
    re.compile(r"\[\s*MAS\s+Notice\b[^\]]*\]", re.IGNORECASE),
    re.compile(r"\bPage\s+\d+\s+of\s+\d+\b", re.IGNORECASE),
    re.compile(r"^\s*Monetary Authority of Singapore\s*$", re.IGNORECASE | re.MULTILINE),
]

_QUOTES = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "‒": "-", "−": "-",
    "…": "...",
}


def normalise(text: str) -> str:
    """Collapse whitespace and canonicalise punctuation. Idempotent."""
    if not text:
        return ""
    # NFKC folds ligatures and non-breaking spaces toward ASCII equivalents.
    text = unicodedata.normalize("NFKC", text)
    for src, dst in _QUOTES.items():
        text = text.replace(src, dst)
    for pattern in _FURNITURE:
        text = pattern.sub(" ", text)
    text = text.replace(" ", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_page_number(line: str) -> bool:
    """A line that is nothing but a number is a page number, not a clause."""
    return bool(re.fullmatch(r"\s*\d{1,3}\s*", line))
