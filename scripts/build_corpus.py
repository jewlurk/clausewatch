"""Parse stored documents into sections, then compute deltas across the timeline.

Idempotent: sections and deltas are replaced, not appended, so this can be re-run
after any parser or threshold change.
"""
from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from corpus import deltas_across, parse_version
from parse.sections import extract_pdf_text
from store import R2Store

from db import PostgresVersionRepository, connection

INSTRUMENT_REF = "Notice 626"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    store = R2Store()

    with connection() as conn:
        repo = PostgresVersionRepository(conn)
        regulator_id = repo.regulator_id("MAS")
        with conn.cursor() as cur:
            cur.execute(
                "select id from instruments where regulator_id = %s and external_ref = %s",
                (regulator_id, INSTRUMENT_REF),
            )
            row = cur.fetchone()
        if row is None:
            print(f"FAIL: instrument {INSTRUMENT_REF!r} not found — run the backfill first")
            return 1
        instrument_id = row[0]

        # Deltas reference section ids, so they must go before sections are replaced.
        cleared = repo.delete_deltas_for_instrument(instrument_id)
        if cleared:
            print(f"cleared {cleared} existing deltas before re-parsing\n")

        versions = repo.versions_for(instrument_id)
        print(f"{len(versions)} stored versions\n")

        parsed = []
        for v in versions:
            try:
                data = store.get(v["r2_key"])
                with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                    tmp.write(data)
                    tmp.flush()
                    text = extract_pdf_text(tmp.name)
                pv = parse_version(v["id"], v["r2_key"], text)
            except Exception as exc:  # noqa: BLE001 - one bad PDF must not stop the rest
                repo.mark_parse_failed(v["id"], f"{type(exc).__name__}: {exc}")
                print(f"  id={v['id']:<3} PARSE FAILED: {type(exc).__name__}: {exc}")
                continue

            repo.replace_sections(pv.version_id, pv.sections)
            # instrument_versions.issue_date is the date *this version* was issued —
            # i.e. its revision date. The instrument's original issue date is a
            # property of the instrument, not of each version, and using it here made
            # every version appear to date from 2015.
            repo.set_version_dates(pv.version_id, pv.version_date, pv.effective_date)
            parsed.append(pv)

            kind = (
                "tracked" if pv.is_tracked
                else "consolidated" if pv.is_consolidated
                else "amendment"
            )
            print(
                f"  id={pv.version_id:<3} {len(pv.sections):>3} sections  "
                f"{pv.version_date!s:<12} {kind}"
            )

        pairs = deltas_across(parsed)
        print(f"\ntimeline: {len(pairs) + 1} consolidated versions, "
              f"{len(pairs)} consecutive comparisons\n")

        total = 0
        for older, newer, deltas in pairs:
            written = repo.replace_deltas(
                instrument_id=instrument_id,
                from_version_id=older.version_id,
                to_version_id=newer.version_id,
                deltas=deltas,
            )
            total += written
            print(f"  {older.version_date} -> {newer.version_date}: {written} deltas")

        print(f"\n{total} deltas written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
