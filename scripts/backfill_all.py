"""Backfill every tracked instrument's published history.

Replaces the single-instrument backfill. Idempotent: dedup is on content hash, so
re-running fetches the same documents and records nothing new.

One shared PoliteClient across all instruments, so the 2s rate limit applies to the
whole run rather than resetting per instrument — a five-instrument backfill is the
most likely moment to get our IP blocked.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from backfill import backfill_instrument
from crawler.http import BlockedError, PoliteClient
from instruments import MAS_INSTRUMENTS
from store import R2Store

from db import PostgresVersionRepository, connection

# §13 per-run cap, per instrument.
MAX_DOCUMENTS = 60


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    store = R2Store()
    failures = 0

    with connection() as conn:
        repo = PostgresVersionRepository(conn)
        regulator_id = repo.regulator_id("MAS")

        with PoliteClient() as client:
            for spec in MAS_INSTRUMENTS:
                instrument_id = repo.upsert_instrument(
                    regulator_id=regulator_id,
                    external_ref=spec.external_ref,
                    title=spec.title,
                    instrument_type=spec.instrument_type,
                    source_url=spec.landing_url,
                    applies_to=spec.applies_to,
                )
                try:
                    report = backfill_instrument(
                        client=client,
                        store=store,
                        repository=repo,
                        landing_url=spec.landing_url,
                        instrument_ref=spec.external_ref,
                        instrument_id=instrument_id,
                        max_documents=MAX_DOCUMENTS,
                    )
                except BlockedError as exc:
                    print(f"{spec.external_ref}: ABORTED — {exc}")
                    failures += 1
                    break
                except Exception as exc:  # noqa: BLE001
                    print(f"{spec.external_ref}: FAILED — {type(exc).__name__}: {exc}")
                    failures += 1
                    continue

                print(report.summary())
                for err in report.errors:
                    print(f"    {err}")
                failures += report.failed

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
