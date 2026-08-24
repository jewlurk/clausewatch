"""PDF -> sections (clauses).

Granularity decision: a section is a **decimal clause** ("6.14"), not a sub-item
("6.14(a)(i)"). Sub-item text is folded into its parent clause body. Reason, verified
against real fixtures: MAS lays sub-items out in a label column and a text column, and
PDF extraction of that is fragile. Clause granularity is also the right product unit —
customers map controls to "Notice 626 para 6.14", and an alert says that clause changed.

Extraction uses LAParams(boxes_flow=None). With pdfminer's default column detection,
"(i)/(ii)/(iii)" labels are emitted as a block *before* their body text; strict reading
order keeps each label with its text.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams

from .normalise import is_page_number, normalise

# A clause line. Two real layouts occur in MAS PDFs and both must be handled:
#   "6.14   Where there is..."   number and body on one line
#   "1.1"                        number alone, body on the following lines
# Verified: 39 of ~130 clauses in Notice 626 (2025) use the second form. Requiring
# same-line body silently dropped all of them.
# Requiring at least one dot is what keeps bare page numbers out.
# The trailing letter matters: MAS inserts amendments as "6.14A", "6.14B" rather than
# renumbering the document. Dropping the letter merged four distinct clauses into one
# key and left a stray "A"/"B" at the head of each body.
CLAUSE_RE = re.compile(r"^\s*(\d+(?:\.\d+)+[A-Z]?)[\.\)]?\s*(.*)$")

# Headings are short all-caps lines. Length-capped so an all-caps run inside a
# sentence cannot split a clause.
MAX_HEADING_LEN = 80

# Structural containers that restart numbering. Kept as a separate key namespace so
# "Appendix 1 para 1" never collides with body "1".
CONTAINER_RE = re.compile(r"^\s*(ANNEX|APPENDIX|SCHEDULE|PART)\s+([A-Z0-9]+)\b\.?\s*$", re.IGNORECASE)

# An all-caps line is a heading ("INTRODUCTION", "DEFINITIONS").
HEADING_RE = re.compile(r"^\s*[A-Z][A-Z \-/&,'()]{3,}$")


def sort_key(section_key: str) -> tuple[tuple[int, ...], str]:
    """Comparable form of a clause key: '6.14B' -> ((6, 14), 'B')."""
    match = re.fullmatch(r"(\d+(?:\.\d+)*)([A-Z]?)", section_key)
    if not match:
        return ((), "")
    numbers = tuple(int(part) for part in match.group(1).split("."))
    return (numbers, match.group(2))


@dataclass
class Section:
    section_key: str
    depth: int
    ordinal: int
    heading: str | None
    body: str

    @property
    def body_sha256(self) -> str:
        return hashlib.sha256(self.body.encode("utf-8")).hexdigest()


def extract_pdf_text(path: str | Path) -> str:
    return extract_text(str(path), laparams=LAParams(boxes_flow=None))


def parse_sections(text: str) -> list[Section]:
    """Split document text into clause-level sections, in document order."""
    sections: list[Section] = []
    heading: str | None = None
    container: str | None = None
    key: str | None = None
    last_key: tuple[tuple[int, ...], str] | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal key, buf
        if key is None:
            return
        body = normalise(" ".join(buf))
        if body:
            full_key = f"{container} {key}" if container else key
            sections.append(
                Section(
                    section_key=full_key,
                    depth=full_key.count(".") + 1,
                    ordinal=len(sections),
                    heading=heading,
                    body=body,
                )
            )
        key, buf = None, []

    for raw in text.split("\n"):
        line = raw.rstrip()
        if not line.strip() or is_page_number(line):
            continue

        container_match = CONTAINER_RE.match(line)
        if container_match:
            flush()
            container = f"{container_match.group(1).title()} {container_match.group(2)}"
            heading = None
            last_key = None  # containers restart numbering
            continue

        clause_match = CLAUSE_RE.match(line)
        if clause_match:
            candidate = clause_match.group(1)
            # Clause numbers advance monotonically in a legal instrument. A number that
            # goes backwards is a wrapped cross-reference that happens to start a line
            # ("...paragraphs 11.3 / to 11.8..."), not a new clause. Verified: this is
            # the only false clause start in the 2025 fixture.
            if last_key is not None and sort_key(candidate) <= last_key:
                if key is not None:
                    buf.append(line)
                continue
            flush()
            key = candidate
            last_key = sort_key(candidate)
            rest = clause_match.group(2).strip()
            buf = [rest] if rest else []
            continue

        # A heading ends the current clause; it belongs to the clauses that follow.
        if HEADING_RE.match(line) and len(line.strip()) <= MAX_HEADING_LEN:
            flush()
            heading = normalise(line)
            continue

        if key is not None:
            buf.append(line)

    flush()
    return sections


def parse_pdf(path: str | Path) -> list[Section]:
    return parse_sections(extract_pdf_text(path))
