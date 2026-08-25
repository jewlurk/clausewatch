"""Parse stored documents into sections, then compute deltas across each timeline.

Runs for every tracked instrument. Idempotent: sections and deltas are replaced, not
appended, so this can be re-run after any parser or threshold change.
"""
from __future__ import annotations

import logging
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from corpus import deltas_across, parse_version
from instruments import MAS_INSTRUMENTS
from parse.sections import extract_pdf_text
from store import R2Store

from db import PostgresVersionRepository, connection


def build_one(repo, store, instrument_id: int, ref: str) -> tuple[int, int]:
    # Deltas reference section ids, so they must go before sections are replaced.
    repo.delete_deltas_for_instrument(instrument_id)

    parsed = []
    for v in repo.versions_for(instrument_id):
        try:
            data = store.get(v["r2_key"])
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                tmp.write(data)
                tmp.flush()
                text = extract_pdf_text(tmp.name)
            pv = parse_version(v["id"], v["r2_key"], text)
        except Exception as exc:  # noqa: BLE001 - one bad PDF must not stop the rest
            repo.mark_parse_failed(v["id"], f"{type(exc).__name__}: {exc}")
            print(f"    id={v['id']} PARSE FAILED: {type(exc).__name__}: {exc}")
            continue

        repo.replace_sections(pv.version_id, pv.sections)
        # issue_date holds the date *this version* was issued, i.e. its revision date.
        repo.set_version_dates(pv.version_id, pv.version_date, pv.effective_date)
        parsed.append(pv)

    pairs = deltas_across(parsed)
    total = 0
    for older, newer, deltas in pairs:
        total += repo.replace_deltas(
            instrument_id=instrument_id,
            from_version_id=older.version_id,
            to_version_id=newer.version_id,
            deltas=deltas,
        )

    usable = len([p for p in parsed if p.usable])
    print(
        f"  {ref}: {len(parsed)} parsed, {usable} consolidated versions, "
        f"{len(pairs)} comparisons, {total} deltas"
    )
    return usable, total


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    store = R2Store()
    versions_total = deltas_total = 0

    with connection() as conn:
        repo = PostgresVersionRepository(conn)
        regulator_id = repo.regulator_id("MAS")

        for spec in MAS_INSTRUMENTS:
            with conn.cursor() as cur:
                cur.execute(
                    "select id from instruments where regulator_id = %s and external_ref = %s",
                    (regulator_id, spec.external_ref),
                )
                row = cur.fetchone()
            if row is None:
                print(f"  {spec.external_ref}: not backfilled yet — skipping")
                continue
            versions, deltas = build_one(repo, store, row[0], spec.external_ref)
            versions_total += versions
            deltas_total += deltas

    print(f"\n{versions_total} consolidated versions, {deltas_total} deltas total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
