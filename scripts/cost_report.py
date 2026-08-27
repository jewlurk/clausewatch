"""Weekly cost and health report (T29, brief §13).

§13 asks for this "before the first paid API call, not after the first surprise bill" —
and the pipeline is already spending on the API. It gathers what a budget page needs and
raises the alarms §13 names:

  * LLM tokens this calendar month, and the USD they cost, from llm_usage (migration
    0008). The deterministic kill switch already lives in EnrichmentBudget; this is the
    measurement that lets anyone see the budget before it is hit.
  * Supabase database size against the 500 MB free tier, with the §13 alarm at 350 MB.
  * R2 object storage against the 10 GB free tier.
  * Corpus and tenant row counts, so growth is visible over time.

It prints the report and, when Resend is configured, emails it (T26's transport, reused).
No email configured is not a failure — it prints and exits, exactly like enrichment
without an LLM key. The one thing that changes the exit code is a breached alarm: the
run finishes green normally, and non-zero when the database or R2 crosses its alarm, so
a threshold cannot be crossed silently.

    python scripts/cost_report.py            # print (and email if configured)
    python scripts/cost_report.py --no-email # never email, just print
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from cost import db_threshold, llm_cost_usd, r2_threshold

from db import connect


def db_size_mb(cur) -> float:
    cur.execute("select pg_database_size(current_database())")
    return cur.fetchone()[0] / 1_000_000


def month_to_date_tokens(cur) -> list[dict]:
    cur.execute(
        """
        select model, sum(calls) as calls,
               sum(input_tokens) as input_tokens,
               sum(output_tokens) as output_tokens,
               sum(summarised) as summarised, sum(rejected) as rejected
          from llm_usage
         where created_at >= date_trunc('month', now())
         group by model
        """
    )
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]


def counts(cur) -> dict[str, int]:
    out: dict[str, int] = {}
    for table in ("instruments", "instrument_versions", "sections", "deltas",
                  "organisations", "control_mappings", "alerts", "usage_events"):
        # Identifiers are a fixed literal tuple above, never user input.
        cur.execute(f"select count(*) from {table}")
        out[table] = cur.fetchone()[0]
    return out


def r2_usage() -> tuple[int, int] | None:
    """(objects, bytes), or None when R2 credentials are not present."""
    if not all(os.environ.get(k) for k in
               ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")):
        return None
    from store import R2Store

    return R2Store().usage()


def build_report() -> tuple[str, bool]:
    """Return (report text, any alarm breached)."""
    lines = [f"Clausewatch cost & health — {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}", ""]
    breached = False

    conn = connect()
    try:
        with conn.cursor() as cur:
            db = db_threshold(db_size_mb(cur))
            lines.append(db.line())
            breached = breached or db.breached

            r2 = r2_usage()
            if r2 is None:
                lines.append("R2 storage: not checked (credentials not present)")
            else:
                objects, size_bytes = r2
                t = r2_threshold(size_bytes)
                lines.append(f"{t.line()}  ({objects} objects)")
                breached = breached or t.breached

            lines.append("")
            lines.append("LLM tokens, month to date:")
            usage = month_to_date_tokens(cur)
            if not usage:
                lines.append("  none this month")
            month_cost = 0.0
            for u in usage:
                cost = llm_cost_usd(u["model"], u["input_tokens"], u["output_tokens"])
                cost_str = f"USD {cost:.2f}" if cost is not None else "unpriced model"
                if cost is not None:
                    month_cost += cost
                lines.append(
                    f"  {u['model']}: {u['calls']} calls, "
                    f"{u['input_tokens']} in / {u['output_tokens']} out, "
                    f"{u['summarised']} summarised, {u['rejected']} rejected — {cost_str}"
                )
            lines.append(f"  month total: USD {month_cost:.2f}")

            lines.append("")
            lines.append("Corpus and tenants:")
            for table, n in counts(cur).items():
                lines.append(f"  {table}: {n}")
    finally:
        conn.close()

    if breached:
        lines.append("")
        lines.append("ALARM: a resource crossed its alarm threshold — see the lines "
                     "marked ALARM above. Mitigation for the database: archive older "
                     "versions' section bodies to R2 (§13).")
    return "\n".join(lines), breached


def maybe_email(report: str, breached: bool) -> None:
    from notify import ResendClient, ResendError

    client = ResendClient()
    to = os.environ.get("FOUNDER_EMAIL", "")
    if not client.configured or not to:
        print("\n(email not sent: RESEND_API_KEY / ALERT_FROM / FOUNDER_EMAIL not all set)")
        return
    subject = ("Clausewatch: RESOURCE ALARM" if breached
               else f"Clausewatch weekly cost report — {datetime.now(timezone.utc):%-d %b %Y}")
    body = f"<pre style='font:13px ui-monospace,Menlo,monospace'>{report}</pre>"
    try:
        client.send(to=to, subject=subject, html=body)
        print(f"\n(report emailed to {to})")
    except ResendError as exc:
        print(f"\n(email failed, report still valid: {exc})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-email", action="store_true", help="print only, never email")
    args = ap.parse_args()

    report, breached = build_report()
    print(report)
    if not args.no_email:
        maybe_email(report, breached)

    # Green normally; non-zero on a breached alarm so CI surfaces it and the founder is
    # notified by the workflow's own failure alert even if email is not configured.
    return 1 if breached else 0


if __name__ == "__main__":
    raise SystemExit(main())
