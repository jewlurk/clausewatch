"""Schema-drift detection (T31, brief §31).

"Alert us before it alerts a customer." MAS can change three things that silently
corrupt the corpus:

  * their CMS, so the landing page no longer links PDFs the way we parse — we discover
    nothing, and an instrument quietly loses its versions;
  * their PDF layout, so a consolidated notice parses to a handful of clauses instead
    of a full tree — the differ then reports garbage or nothing;
  * their header wording, so the "Last revised on" date stops extracting — dated
    versions drop off the timeline.

Every one of those surfaces as a measurable symptom in the corpus *after* a crawl. This
module holds the pure invariant checks; scripts/check_drift.py gathers the live numbers
and applies them. Keeping the thresholds here, separate from the SQL, is what lets them
be tested without a database — the same reason cost.py is split from cost_report.py.

The baselines are deliberately loose. A drift alarm that cries wolf gets muted, and a
muted alarm is worse than none — so these fire on a structural break (an instrument with
*no* consolidated versions, a consolidated notice that parsed to almost nothing), not on
a normal revision.
"""
from __future__ import annotations

from dataclasses import dataclass

# A consolidated MAS notice parses to ~65-170 clauses. The smallest real one in the
# corpus (TCA-N03, 2009) is 65. Below this floor, a version that *should* be a full
# notice almost certainly hit a parse or format change, not a genuinely tiny notice.
MIN_CONSOLIDATED_SECTIONS = 40

# Every tracked instrument should carry at least this many consolidated versions on its
# timeline. One is enough to serve; zero means it vanished from the corpus entirely,
# which is the discovery-drift symptom.
MIN_CONSOLIDATED_VERSIONS = 1

CRITICAL, WARNING = "CRITICAL", "WARNING"


@dataclass(frozen=True)
class InstrumentHealth:
    """Post-crawl facts about one instrument, read from the database."""

    external_ref: str
    versions_total: int          # every stored version (consolidated, tracked, amendment)
    consolidated_versions: int   # versions that reached the timeline
    dated_versions: int          # consolidated versions with an extractable date
    latest_section_count: int    # clauses parsed from the newest consolidated version
    failed_parses: int           # instrument_versions rows with parse_status = 'failed'


@dataclass(frozen=True)
class Finding:
    ref: str
    level: str
    message: str

    def line(self) -> str:
        return f"  [{self.level}] {self.ref}: {self.message}"


def check_instrument(h: InstrumentHealth) -> list[Finding]:
    """Invariants for one instrument. CRITICAL means the corpus is probably wrong."""
    out: list[Finding] = []

    if h.versions_total == 0:
        out.append(Finding(h.external_ref, CRITICAL,
                           "no versions stored at all — discovery or landing page changed"))
        return out  # nothing else is meaningful without any documents

    if h.consolidated_versions < MIN_CONSOLIDATED_VERSIONS:
        out.append(Finding(
            h.external_ref, CRITICAL,
            f"{h.versions_total} document(s) stored but 0 parsed as a consolidated "
            "notice — PDF layout or clause numbering likely changed"))

    if h.consolidated_versions and h.latest_section_count < MIN_CONSOLIDATED_SECTIONS:
        out.append(Finding(
            h.external_ref, CRITICAL,
            f"newest consolidated version parsed to only {h.latest_section_count} "
            f"clauses (floor {MIN_CONSOLIDATED_SECTIONS}) — probable parse drift"))

    if h.consolidated_versions and h.dated_versions == 0:
        out.append(Finding(
            h.external_ref, CRITICAL,
            "no consolidated version has an extractable date — header format likely "
            "changed; the whole timeline would be empty"))

    if h.failed_parses:
        out.append(Finding(
            h.external_ref, WARNING,
            f"{h.failed_parses} document(s) failed to parse"))

    return out


def check_corpus(
    healths: list[InstrumentHealth], expected_instruments: int
) -> list[Finding]:
    """Whole-corpus invariants plus every per-instrument check."""
    out: list[Finding] = []
    if len(healths) < expected_instruments:
        out.append(Finding(
            "corpus", CRITICAL,
            f"{len(healths)} instruments present, expected {expected_instruments} — "
            "one or more were not crawled"))
    for h in healths:
        out.extend(check_instrument(h))
    return out


def has_critical(findings: list[Finding]) -> bool:
    return any(f.level == CRITICAL for f in findings)
