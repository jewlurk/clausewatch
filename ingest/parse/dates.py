"""Issue and effective date extraction. Brief T4.

Verified against real MAS PDFs. The header is consistent:

    MAS Notice 626
    28 March 2024
    Last revised on 30 June 2025
    (Refer to endnotes for history of amendments)

The first date is when the instrument was issued. "Last revised on <date>" marks the
specific version, so it is what orders versions on a timeline — two versions of the
same instrument share an issue date but differ in revision date.

Effective dates live in the body: "This Notice shall take effect from 1 April 2024."
They can be staggered ("except for paragraphs 4, 5 ... which take effect from
24 July 2015"), in which case the earliest is recorded.
"""
from __future__ import annotations

import re
from datetime import date

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_DATE = r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})"
_DATE_RE = re.compile(_DATE)
_REVISED_RE = re.compile(r"[Ll]ast\s+revised\s+on\s+" + _DATE)
_EFFECT_RE = re.compile(
    r"(?:take[s]?\s+effect|shall\s+take\s+effect|with\s+effect)\s+"
    r"(?:from|on)?\s*" + _DATE,
    re.IGNORECASE,
)


def _to_date(day: str, month: str, year: str) -> date | None:
    m = _MONTHS.get(month.lower())
    if not m:
        return None
    try:
        return date(int(year), m, int(day))
    except ValueError:
        return None


def extract_issue_date(text: str) -> date | None:
    """The first date in the header — when the instrument was originally issued."""
    head = text[:1200]
    match = _DATE_RE.search(head)
    return _to_date(*match.groups()) if match else None


def extract_revision_date(text: str) -> date | None:
    """The "Last revised on" date, if present. Identifies this specific version."""
    match = _REVISED_RE.search(text[:1200])
    return _to_date(*match.groups()) if match else None


# Endnotes list the commencement date of every historical amendment ("MAS Notice 626
# dated 2 July 2007 takes effect..."). Searching the whole document therefore returns
# the oldest date in the instrument's history rather than this version's effective
# date. Verified: the 2015 and 2022 PDFs yielded 2007 and 2009 before this cut.
_ENDNOTES_RE = re.compile(r"\bEndnotes?\b|\bAmendments?\s+to\s+MAS\s+Notice\b", re.IGNORECASE)


def _body_before_endnotes(text: str) -> str:
    match = _ENDNOTES_RE.search(text, pos=len(text) // 2)
    return text[: match.start()] if match else text


def extract_effective_date(text: str) -> date | None:
    """Earliest effective date stated in this version's own text.

    Earliest, because MAS staggers commencement ("except for paragraphs 4, 5 ... which
    take effect from 24 July 2015"); the first date an obligation can bite is the safe
    reading. Endnotes are excluded — see above.
    """
    found = [
        d
        for match in _EFFECT_RE.finditer(_body_before_endnotes(text))
        if (d := _to_date(*match.groups())) is not None
    ]
    return min(found) if found else None


def version_date(text: str) -> date | None:
    """The date that places this version on a timeline.

    Revision date when present, otherwise the issue date. Two versions of one
    instrument share an issue date, so the issue date alone cannot order them.
    """
    return extract_revision_date(text) or extract_issue_date(text)
