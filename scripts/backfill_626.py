"""Backfill MAS Notice 626's published history into the database and R2.

Run from GitHub Actions, where DATABASE_URL and the R2 credentials live.
Idempotent: rerunning fetches the same documents and records nothing new.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from backfill import backfill_instrument
from crawler.http import PoliteClient
from store import R2Store

from db import PostgresVersionRepository, connection

LANDING_URL = "https://www.mas.gov.sg/regulation/notices/notice-626"
INSTRUMENT_REF = "Notice 626"
TITLE = (
    "Prevention of Money Laundering and Countering the Financing of Terrorism - Banks"
)

# §13 per-run cap: a MAS restructure exposing thousands of links must not drain us.
MAX_DOCUMENTS = 60


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    with connection() as conn:
        repo = PostgresVersionRepository(conn)
        instrument_id = repo.upsert_instrument(
            regulator_id=repo.regulator_id("MAS"),
            external_ref=INSTRUMENT_REF,
            title=TITLE,
            instrument_type="notice",
            source_url=LANDING_URL,
        )
        print(f"instrument id: {instrument_id}")

        with PoliteClient() as client:
            report = backfill_instrument(
                client=client,
                store=R2Store(),
                repository=repo,
                landing_url=LANDING_URL,
                instrument_ref=INSTRUMENT_REF,
                instrument_id=instrument_id,
                max_documents=MAX_DOCUMENTS,
            )

        print("\n" + report.summary())
        for err in report.errors:
            print(f"  error: {err}")

        versions = repo.versions_for(instrument_id)
        print(f"\nversions now stored: {len(versions)}")
        for v in versions:
            print(f"  id={v['id']:<4} sha={v['content_sha256'][:12]}  {v['r2_key']}")

    return 1 if report.failed and report.created == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
