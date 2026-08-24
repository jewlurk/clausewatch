"""T14 — backfill an instrument's published history.

MAS links an instrument's full version history from its landing page: Notice 626's
page carried 15 distinct PDFs spanning 2014-2025 (verified 2026-08-25). So backfill is
just "fetch every PDF the landing page links", with the dedup rule doing the rest.

Runs behind the same rate limiter as the daily crawl — a backfill is the most likely
moment to get our IP blocked, because it fetches many documents in one go.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from crawler.http import BlockedError, PoliteClient
from crawler.mas import MasAdapter
from pipeline import Outcome, ingest_document
from store import ObjectStore

log = logging.getLogger(__name__)


@dataclass
class BackfillReport:
    instrument_ref: str
    discovered: int = 0
    created: int = 0
    unchanged: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.instrument_ref}: {self.discovered} linked, {self.created} new, "
            f"{self.unchanged} already known, {self.failed} failed"
        )


def backfill_instrument(
    *,
    client: PoliteClient,
    store: ObjectStore,
    repository,
    landing_url: str,
    instrument_ref: str,
    instrument_id: int,
    regulator_code: str = "MAS",
    max_documents: int | None = None,
) -> BackfillReport:
    """Fetch every version linked from an instrument's landing page.

    `max_documents` is the §13 per-run cap: if MAS restructures and a page suddenly
    exposes thousands of links, we stop rather than hammer them.
    """
    report = BackfillReport(instrument_ref=instrument_ref)

    landing = client.fetch(landing_url)
    html = landing.content.decode("utf-8", "ignore")
    refs = MasAdapter().discover(html, instrument_ref)
    report.discovered = len(refs)

    if max_documents is not None and len(refs) > max_documents:
        log.warning(
            "%s: %d documents exceeds cap of %d — truncating",
            instrument_ref,
            len(refs),
            max_documents,
        )
        refs = refs[:max_documents]

    for ref in refs:
        try:
            result = ingest_document(
                client=client,
                store=store,
                repository=repository,
                regulator_code=regulator_code,
                instrument_id=instrument_id,
                instrument_ref=instrument_ref,
                url=ref.url,
            )
        except BlockedError:
            # Being served block pages means we should stop entirely, not keep going.
            report.failed += 1
            report.errors.append(f"{ref.url}: blocked by host — aborting backfill")
            log.error("blocked by host at %s — aborting", ref.url)
            break
        except Exception as exc:  # noqa: BLE001 - one bad document must not stop the rest
            report.failed += 1
            report.errors.append(f"{ref.url}: {type(exc).__name__}: {exc}")
            log.warning("failed %s: %s", ref.url, exc)
            continue

        if result.outcome is Outcome.CREATED:
            report.created += 1
            log.info("new version %s -> %s", ref.url.split("/")[-1], result.sha256[:12])
        else:
            report.unchanged += 1

    return report
