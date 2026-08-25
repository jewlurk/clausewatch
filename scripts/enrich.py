"""Generate plain-language summaries for material changes (T28).

Runs after the corpus is built. Optional by design: with no ANTHROPIC_API_KEY the
script exits cleanly and the pipeline continues, because deltas without summaries are
still a usable product.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from enrich.summarise import EnrichmentBudget, build_client, summarise_change

from db import PostgresVersionRepository, connection

# Default keeps a daily run short and its cost predictable. Raise it via the
# environment to clear a backlog — the token ceiling in EnrichmentBudget is what
# actually bounds spend, not this.
BATCH = int(os.environ.get("ENRICH_BATCH", "400"))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    client = build_client()
    if client is None:
        print("ANTHROPIC_API_KEY not set — skipping enrichment (pipeline unaffected)")
        return 0

    budget = EnrichmentBudget()
    done = skipped = 0

    with connection() as conn:
        repo = PostgresVersionRepository(conn)
        pending = repo.deltas_needing_summary(BATCH)
        print(f"{len(pending)} material changes without a summary")

        for row in pending:
            if budget.exhausted:
                print("token ceiling reached — stopping enrichment, pipeline continues")
                break
            result = summarise_change(
                client,
                instrument_ref=row["external_ref"],
                section_key=row["section_key"],
                old_body=row["old_body"],
                new_body=row["new_body"],
                budget=budget,
            )
            if result is None:
                skipped += 1
                continue
            repo.save_summary(
                row["id"],
                summary=result.summary,
                obligation_change=result.obligation_change,
                action_hint=result.action_hint,
            )
            done += 1

    print(f"\n{done} summarised, {skipped} skipped")
    print(budget.report())
    if budget.rejected:
        print(f"prescriptive rejections: {', '.join(budget.rejected[:5])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
