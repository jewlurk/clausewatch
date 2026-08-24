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
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pdfminer.high_level import extract_pages, extract_text
from pdfminer.layout import LAParams, LTChar, LTTextContainer

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

# Characters smaller than this fraction of the document's modal font size are footnote
# bodies or superscript reference markers, not clause text. See extract_pdf_text.
FOOTNOTE_SIZE_RATIO = 0.9

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


def _char_sizes(pages) -> Counter:
    sizes: Counter = Counter()
    for page in pages:
        for element in page:
            if not isinstance(element, LTTextContainer):
                continue
            for line in element:
                if not hasattr(line, "__iter__"):
                    continue
                for ch in line:
                    if isinstance(ch, LTChar) and ch.get_text().strip():
                        sizes[round(ch.size, 1)] += 1
    return sizes


def split_by_font(path: str | Path) -> tuple[str, str]:
    """Split a PDF into (body text, footnote text) by font size.

    Footnotes are the single largest source of false positives. MAS renumbers them
    whenever one is inserted, so an untouched clause reads "institutions4" in one
    version and "institutions6" in the next, and markers concatenate onto references
    ("11.5" + footnote "5" -> "11.55"). Footnote bodies also migrate between clauses as
    page breaks shift. Measured on the 2024->2025 pair, that noise caused 9 of 11 false
    positives.

    They are separable by font: body text is the document's modal size (13.0pt in
    Notice 626) and footnotes are smaller (~10pt). The threshold is a fraction of the
    modal size, so it survives a document set in a different base size.

    Footnote text is returned rather than discarded: dropping it entirely hid two real
    changes (paras 4.1 and 6.3 of the June 2025 amendment). Missing a real change is
    worse than a false positive for a compliance product.
    """
    laparams = LAParams(boxes_flow=None)
    pages = list(extract_pages(str(path), laparams=laparams))
    sizes = _char_sizes(pages)
    if not sizes:
        return "", ""
    floor = sizes.most_common(1)[0][0] * FOOTNOTE_SIZE_RATIO

    body: list[str] = []
    footnotes: list[str] = []
    for page in pages:
        for element in page:
            if not isinstance(element, LTTextContainer):
                continue
            for line in element:
                if not hasattr(line, "__iter__"):
                    continue
                big, small = [], []
                for ch in line:
                    if not isinstance(ch, LTChar):
                        continue
                    (big if ch.size >= floor else small).append(ch.get_text())
                if "".join(big).strip():
                    body.append("".join(big).rstrip("\n"))
                if "".join(small).strip():
                    footnotes.append("".join(small).rstrip("\n"))
    return "\n".join(body), "\n".join(footnotes)


def extract_pdf_text(path: str | Path, drop_footnotes: bool = True) -> str:
    """Body text only (default), or the raw extraction including footnotes."""
    if not drop_footnotes:
        return extract_text(str(path), laparams=LAParams(boxes_flow=None))
    return split_by_font(path)[0]


# A footnote body: a number, then substantial text. Inline superscript markers survive
# the font split as bare digits on their own line; the length floor discards those.
FOOTNOTE_RE = re.compile(r"^\s*(\d{1,3})\s+(\S.{15,})$")


def parse_footnotes(footnote_text: str) -> list[Section]:
    """Footnotes as their own sections, keyed "Footnote N".

    Renumbering is then handled by the differ's existing Pass 2: when footnote 4
    becomes footnote 6 with identical text, that is a RENUMBERED delta (severity 2),
    not a change to every clause that referenced it.
    """
    sections: list[Section] = []
    key: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal key, buf
        if key is None:
            return
        body = normalise(" ".join(buf))
        if body:
            sections.append(
                Section(
                    section_key=f"Footnote {key}",
                    depth=1,
                    ordinal=len(sections),
                    heading="FOOTNOTES",
                    body=body,
                )
            )
        key, buf = None, []

    for raw in footnote_text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        match = FOOTNOTE_RE.match(line)
        if match:
            flush()
            key, buf = match.group(1), [match.group(2)]
        elif re.fullmatch(r"[\d\s]+", line):
            # Inline superscript markers survive the font split as bare digits. They
            # are references, not footnote text, and they renumber on every amendment —
            # appending them would reintroduce the noise this split exists to remove.
            continue
        elif key is not None:
            buf.append(line)

    flush()
    return sections


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


def parse_pdf(path: str | Path, include_footnotes: bool = False) -> list[Section]:
    """Clause sections, optionally followed by footnote sections.

    Footnotes default OFF. Measured on the 2024->2025 pair they raise recall from
    77% to 96% — they carry real amendments, such as cross-references renumbered from
    11A.x to 11.x — but they also add 9 spurious deltas, taking the false-positive rate
    from 0% to 27%. The residual noise is sub-item labels ("(a)"/"(c)") reordering under
    PDF column extraction, not a differ fault. Until that extraction is stable, noisy
    alerts would cost more trust than the extra recall buys. See
    docs/threshold-tuning.md.
    """
    body_text, footnote_text = split_by_font(path)
    sections = parse_sections(body_text)
    if not include_footnotes:
        return sections
    offset = len(sections)
    for footnote in parse_footnotes(footnote_text):
        footnote.ordinal += offset
        sections.append(footnote)
    return sections
