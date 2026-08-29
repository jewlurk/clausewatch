"""Schema-drift check (T31, §31).

Runs after the corpus is rebuilt. Reads the post-crawl state of every tracked
instrument and applies the invariants in ingest/drift.py. Prints a health table and
exits non-zero if any CRITICAL finding is present, so the pipeline surfaces MAS-side
format changes to us the same day — before a customer sees a broken changelog.

No load on MAS: this reads the database the crawl just wrote, not the MAS site.

    python scripts/check_drift.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from drift import InstrumentHealth, check_corpus, has_critical
from instruments import MAS_INSTRUMENTS

from db import connect

EXPECTED_INSTRUMENTS = len(MAS_INSTRUMENTS)


def gather(cur) -> list[InstrumentHealth]:
    """One InstrumentHealth per tracked instrument, from the live corpus.

    'Consolidated' here means a version that reached the timeline: it has an
    extractable date and a full clause tree. That is mirrored by the count of its
    sections, so the section count of the newest such version is the parse-health
    signal.
    """
    healths: list[InstrumentHealth] = []
    for spec in MAS_INSTRUMENTS:
        cur.execute(
            "select id from instruments where external_ref = %s", (spec.external_ref,))
        row = cur.fetchone()
        if row is None:
            # No instrument row at all — represented as a total blank so check_corpus
            # flags the missing-instrument case.
            healths.append(InstrumentHealth(spec.external_ref, 0, 0, 0, 0, 0))
            continue
        instrument_id = row[0]

        cur.execute(
            "select count(*) from instrument_versions where instrument_id = %s",
            (instrument_id,))
        versions_total = cur.fetchone()[0]

        cur.execute(
            "select count(*) from instrument_versions "
            "where instrument_id = %s and parse_status = 'failed'", (instrument_id,))
        failed_parses = cur.fetchone()[0]

        # A version is on the timeline when it has sections and a date. Section counts
        # per version, newest first by issue_date.
        cur.execute(
            """
            select v.id, v.issue_date, count(s.id) as n
              from instrument_versions v
              left join sections s on s.version_id = v.id
             where v.instrument_id = %s
             group by v.id, v.issue_date
            """,
            (instrument_id,))
        rows = cur.fetchall()
        consolidated = [(vid, d, n) for (vid, d, n) in rows if n >= 40]
        dated = [r for r in consolidated if r[1] is not None]
        latest = max(dated, key=lambda r: r[1])[2] if dated else (
            max(consolidated, key=lambda r: r[2])[2] if consolidated else 0)

        healths.append(InstrumentHealth(
            external_ref=spec.external_ref,
            versions_total=versions_total,
            consolidated_versions=len(consolidated),
            dated_versions=len(dated),
            latest_section_count=latest,
            failed_parses=failed_parses,
        ))
    return healths


def main() -> int:
    conn = connect()
    try:
        with conn.cursor() as cur:
            healths = gather(cur)
    finally:
        conn.close()

    print(f"{'instrument':<13}{'versions':>9}{'consol.':>9}{'dated':>7}"
          f"{'latest §':>10}{'failed':>8}")
    for h in sorted(healths, key=lambda h: h.external_ref):
        print(f"{h.external_ref:<13}{h.versions_total:>9}{h.consolidated_versions:>9}"
              f"{h.dated_versions:>7}{h.latest_section_count:>10}{h.failed_parses:>8}")

    findings = check_corpus(healths, EXPECTED_INSTRUMENTS)
    print()
    if not findings:
        print("No schema drift: every instrument parsed to a dated, full-size timeline.")
        return 0

    for f in findings:
        print(f.line())

    if has_critical(findings):
        print("\nDRIFT DETECTED — a MAS format change has probably broken the corpus. "
              "Investigate before the next site publish.")
        return 1
    print("\nWarnings only — no critical drift.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
