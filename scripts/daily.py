"""Daily pipeline: crawl every tracked instrument, rebuild the corpus, record the run.

Runs unattended on a schedule. Three things matter here beyond the happy path:

* The run is recorded in `crawl_runs` whatever happens. The public site shows
  "last checked on <date>", and in a month where nothing changed that line is the only
  thing distinguishing "nothing happened" from "nobody looked".
* A block page aborts the run rather than continuing. Getting our IP banned by MAS
  would end the project.
* Exit code is non-zero on failure so GitHub surfaces it, but the corpus is left
  intact — a failed crawl must never leave a half-updated corpus on the public site.
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

MAX_DOCUMENTS = 60


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    store = R2Store()
    docs = new_versions = failures = 0
    error: str | None = None

    with connection() as conn:
        repo = PostgresVersionRepository(conn)
        regulator_id = repo.regulator_id("MAS")
        run_id = repo.start_crawl_run(regulator_id)

        try:
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
                    report = backfill_instrument(
                        client=client,
                        store=store,
                        repository=repo,
                        landing_url=spec.landing_url,
                        instrument_ref=spec.external_ref,
                        instrument_id=instrument_id,
                        max_documents=MAX_DOCUMENTS,
                    )
                    docs += report.discovered
                    new_versions += report.created
                    failures += report.failed
                    print(report.summary())
        except BlockedError as exc:
            error = f"blocked by host: {exc}"
            print(f"ABORTED — {error}")
        except Exception as exc:  # noqa: BLE001 - the run must still be recorded
            error = f"{type(exc).__name__}: {exc}"
            print(f"FAILED — {error}")

        status = "ok" if error is None and failures == 0 else "failed"
        repo.finish_crawl_run(
            run_id,
            status=status,
            docs_seen=docs,
            versions_new=new_versions,
            error=error,
        )

    print(f"\n{docs} documents seen, {new_versions} new versions, {failures} failures")
    if new_versions:
        print("NEW VERSIONS FOUND — corpus and site will be rebuilt")
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
