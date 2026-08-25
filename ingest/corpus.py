"""Turn stored raw documents into sections and deltas.

A landing page links more than consolidated notices: amendment notices, cancellation
notices, and MAS's own tracked-changes PDFs all sit alongside the full text. Diffing a
consolidated notice against a two-page amendment notice produces garbage, so versions
are classified first and only consolidated texts are compared.

Classification is by parsed shape, not filename. MAS filenames are inconsistent across
publishing eras ("626-revised-notice-banks.pdf", "mas-notice-626--april-2015.pdf"),
whereas a consolidated notice always parses to a full clause tree and an amendment
notice does not.
"""
from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from datetime import date

from diff.delta import compute_delta
from parse.dates import extract_effective_date, extract_issue_date, version_date
from parse.sections import Section, parse_sections

log = logging.getLogger(__name__)

# A consolidated notice restates the whole instrument. Notice 626 parses to ~120-150
# clauses; amendment and cancellation notices parse to a handful.
CONSOLIDATED_MIN_SECTIONS = 50

# MAS publishes tracked-changes copies alongside clean ones. They contain both old and
# new wording inline, so diffing them yields nonsense. They are excluded from the
# timeline but kept in storage — the tracked copy is the oracle used to measure
# accuracy (see docs/threshold-tuning.md).
TRACKED_MARKERS = (
    "coloured and struck through",
    "represents deletion which will not appear",
)


@dataclass
class ParsedVersion:
    version_id: int
    r2_key: str
    sections: list[Section]
    issue_date: date | None
    effective_date: date | None
    version_date: date | None
    is_consolidated: bool
    is_tracked: bool

    @property
    def usable(self) -> bool:
        """Belongs on the changelog timeline."""
        return self.is_consolidated and not self.is_tracked


def classify(text: str, sections: list[Section]) -> tuple[bool, bool]:
    """Return (is_consolidated, is_tracked)."""
    head = text[:4000].lower()
    is_tracked = any(marker in head for marker in TRACKED_MARKERS)
    is_consolidated = len(sections) >= CONSOLIDATED_MIN_SECTIONS
    return is_consolidated, is_tracked


def parse_version(version_id: int, r2_key: str, text: str) -> ParsedVersion:
    sections = parse_sections(text)
    is_consolidated, is_tracked = classify(text, sections)
    return ParsedVersion(
        version_id=version_id,
        r2_key=r2_key,
        sections=sections,
        issue_date=extract_issue_date(text),
        effective_date=extract_effective_date(text),
        version_date=version_date(text),
        is_consolidated=is_consolidated,
        is_tracked=is_tracked,
    )


def timeline(versions: list[ParsedVersion]) -> list[ParsedVersion]:
    """Usable versions in chronological order.

    A version whose date could not be extracted is excluded, not sorted last. The whole
    basis of a comparison is that one version precedes another; an undated version
    placed arbitrarily in the chain produces a diff between two versions that may not
    be adjacent in reality, which is worse than not diffing it. The exclusion is logged
    so a date-extraction gap surfaces rather than passing as silence.
    """
    usable = [v for v in versions if v.usable]
    dated = [v for v in usable if v.version_date is not None]
    undated = len(usable) - len(dated)
    if undated:
        log.warning(
            "%d consolidated version(s) excluded from the timeline: no date extracted",
            undated,
        )
    return sorted(dated, key=lambda v: v.version_date)


def deltas_across(versions: list[ParsedVersion]) -> list[tuple[ParsedVersion, ParsedVersion, list]]:
    """Compute deltas between each consecutive pair on the timeline."""
    ordered = timeline(versions)
    out = []
    for older, newer in itertools.pairwise(ordered):
        computed = compute_delta(older.sections, newer.sections)
        log.info(
            "%s -> %s: %d deltas",
            older.version_date,
            newer.version_date,
            len(computed),
        )
        out.append((older, newer, computed))
    return out
