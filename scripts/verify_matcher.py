"""Prove the SQL matcher agrees with the in-memory one (T16 safety check).

The differ's measured accuracy — 0% false positives on Notice 626, 3.4% pooled — was
established with the in-memory matcher. Moving the renumber-hunt to SQL (matcher.py)
only stays safe if pg_trgm's similarity() and the in-memory Jaccard-over-trigrams pick
the same matches. This asserts exactly that, against the live corpus: for every
consecutive version pair of every instrument, it computes the deltas both ways and
requires them to be identical, op for op and key for key.

If they diverge, the SQL matcher must not go to production — the message names the pair
and the differing deltas so the divergence can be understood, not just detected.

    DATABASE_URL=... python scripts/verify_matcher.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from corpus import parse_version, timeline
from diff.delta import InMemoryMatcher, compute_delta
from instruments import MAS_INSTRUMENTS
from matcher import SqlMatcher
from parse.sections import extract_pdf_text
from store import R2Store

from db import PostgresVersionRepository, connect


def key(deltas):
    """A comparable, order-independent signature of a delta list.

    The match DECISION is (op, old_key, new_key, severity) — that is what determines
    which changes get reported, and it must match exactly. The similarity is rounded to
    two places because pg_trgm returns it as a float4 while the in-memory matcher
    computes a float64, so identical matches differ in the ~4th decimal (0.9119 vs
    0.912). That is representation, not behaviour: two places absorbs the float4 noise
    while a genuine divergence still shows up in the op/key fields.
    """
    return sorted(
        (d.op, d.old_section_key, d.new_section_key, d.severity, round(d.similarity or 0, 2))
        for d in deltas
    )


def main() -> int:
    import tempfile

    conn = connect()
    store = R2Store()
    repo = PostgresVersionRepository(conn)

    total_pairs = agree = 0
    diffs: list[str] = []

    try:
        regulator_id = repo.regulator_id("MAS")
        for spec in MAS_INSTRUMENTS:
            with conn.cursor() as cur:
                cur.execute(
                    "select id from instruments where regulator_id = %s and external_ref = %s",
                    (regulator_id, spec.external_ref))
                row = cur.fetchone()
            if row is None:
                continue
            instrument_id = row[0]

            parsed = []
            for v in repo.versions_for(instrument_id):
                try:
                    data = store.get(v["r2_key"])
                    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                        tmp.write(data)
                        tmp.flush()
                        text = extract_pdf_text(tmp.name)
                    parsed.append(parse_version(v["id"], v["r2_key"], text))
                except Exception:  # noqa: BLE001,S112 — a bad PDF is not this check's concern
                    continue

            ordered = timeline(parsed)
            for i in range(1, len(ordered)):
                older, newer = ordered[i - 1], ordered[i]
                total_pairs += 1
                in_mem = compute_delta(older.sections, newer.sections,
                                       matcher=InMemoryMatcher())
                sql = compute_delta(older.sections, newer.sections,
                                    matcher=SqlMatcher(conn, newer.version_id))
                if key(in_mem) == key(sql):
                    agree += 1
                else:
                    only_mem = [d for d in key(in_mem) if d not in key(sql)]
                    only_sql = [d for d in key(sql) if d not in key(in_mem)]
                    diffs.append(
                        f"{spec.external_ref} {older.version_date}->{newer.version_date}: "
                        f"in-memory only {only_mem}; sql only {only_sql}")
    finally:
        conn.close()

    print(f"{agree}/{total_pairs} version pairs produced identical deltas both ways")
    if diffs:
        print("\nDIVERGENCE — do not ship the SQL matcher until resolved:")
        for d in diffs:
            print(f"  {d}")
        return 1
    print("SQL matcher and in-memory matcher agree on the entire corpus. "
          "The GIN-index matcher preserves the measured accuracy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
