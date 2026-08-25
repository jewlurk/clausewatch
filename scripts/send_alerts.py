"""Send alert emails (T26).

Runs at the end of the daily pipeline. Generates alerts from the current deltas, then
emails each recipient one digest covering everything they have not been told about.

Design points worth knowing before changing it:

* **One digest per recipient per run, not one email per change.** A MAS revision round
  moves hundreds of clauses at once; a per-change email would be unusable and would
  exhaust the free tier's 100/day in a single evening.
* **Mapped controls lead.** If any change touches a clause the org mapped a control to,
  the mapped-control template is used and the watchlist hits ride along underneath.
* **`notified_at` is set only after the send returns an id.** A crash mid-run repeats a
  send at worst; it never silently drops one.
* **No key configured is not a failure.** The pipeline must run to completion without
  Resend, exactly as it does without an LLM key. It prints what it would have sent.

Dry run:  python scripts/send_alerts.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from notify import Alert, Digest, ResendClient, ResendError, render_digest
from notify.resend import DAILY_CAP

from db import connect

FIELDS = (
    "alert_id", "org_id", "org_name", "recipient", "instrument_ref", "instrument_title",
    "source_url", "section_key", "op", "severity", "revision_date", "effective_date",
    "internal_ref", "ai_summary", "obligation_change",
)


def load_digests(cur, max_rows: int) -> list[Digest]:
    cur.execute("select * from pending_alerts(%s)", (max_rows,))
    rows = [dict(zip(FIELDS, r, strict=True)) for r in cur.fetchall()]

    grouped: OrderedDict[tuple[str, str], list[Alert]] = OrderedDict()
    for row in rows:
        key = (row["recipient"], row["org_name"])
        grouped.setdefault(key, []).append(
            Alert(**{k: row[k] for k in Alert.__dataclass_fields__})
        )
    return [
        Digest(recipient=r, org_name=o, alerts=tuple(a)) for (r, o), a in grouped.items()
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="render and report, send nothing, mark nothing")
    ap.add_argument("--max-rows", type=int, default=500)
    ap.add_argument("--limit", type=int, default=DAILY_CAP,
                    help=f"maximum emails this run (free tier is 100/day; default {DAILY_CAP})")
    args = ap.parse_args()

    conn = connect()
    conn.autocommit = False
    sent = failed = 0
    try:
        with conn.cursor() as cur:
            cur.execute("select generate_alerts()")
            created = cur.fetchone()[0]
            print(f"generate_alerts(): {created} new alert(s)")
            conn.commit()

            digests = load_digests(cur, args.max_rows)
            total = sum(len(d.alerts) for d in digests)
            print(f"{total} unsent alert(s) across {len(digests)} recipient(s)")
            if not digests:
                return 0

            client = ResendClient()
            if not client.configured and not args.dry_run:
                print("\nRESEND_API_KEY / ALERT_FROM not set — nothing sent.")
                print("This is not a failure: the pipeline is complete without email.")
                args.dry_run = True

            if len(digests) > args.limit:
                print(f"WARNING: {len(digests)} recipients exceeds the {args.limit} cap; "
                      f"sending the first {args.limit} and leaving the rest unsent.")
                digests = digests[: args.limit]

            for digest in digests:
                try:
                    subject, html = render_digest(digest)
                except Exception as exc:  # noqa: BLE001 — one bad digest must not stop the run
                    failed += 1
                    print(f"  SKIP  {digest.recipient}: {exc}")
                    continue

                if args.dry_run:
                    print(f"  DRY   {digest.recipient}  ({len(digest.mapped)} mapped, "
                          f"{len(digest.watched)} watched)  subject: {subject}")
                    continue

                try:
                    message_id = client.send(to=digest.recipient, subject=subject, html=html)
                except ResendError as exc:
                    failed += 1
                    print(f"  FAIL  {digest.recipient}: {exc}")
                    continue

                cur.execute(
                    "update alerts set notified_at = now() where id = any(%s)",
                    ([a.alert_id for a in digest.alerts],),
                )
                conn.commit()
                sent += 1
                print(f"  SENT  {digest.recipient}  {len(digest.alerts)} change(s)  "
                      f"id={message_id}  subject: {subject}")
    finally:
        conn.rollback()
        conn.close()

    print(f"\n{sent} sent, {failed} failed")
    return 1 if failed and not sent else 0


if __name__ == "__main__":
    raise SystemExit(main())
