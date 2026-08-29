"""Restore drill (T32, §32) — prove the backup actually restores.

The brief is explicit: an *actual restore performed*, not just configured. A dump that
has never been restored is a belief. This takes the backup scripts/backup.py produces,
restores it into a clean, isolated Postgres, and proves the data round-trips by
comparing row counts table by table against the source.

Two databases:
  DATABASE_URL          the live Supabase database (source of truth for the counts)
  RESTORE_DATABASE_URL  a throwaway Postgres to restore into (a service container in CI)

The restore target is wiped first, so the drill is repeatable and never contaminates
anything real. It is given the same major Postgres version as Supabase (17), so the dump
loads without a version mismatch.

Restore happens in two phases — schema, then data with triggers disabled — because the
`public` dump carries a foreign key from memberships to auth.users, and auth.users is
not in a public-only dump. Disabling triggers during the data load (a superuser can, and
the throwaway container's postgres role is one) lets the corpus and tenant rows load
without that constraint failing. The constraint itself still restores; only its
enforcement during the bulk load is deferred.

    DATABASE_URL=... RESTORE_DATABASE_URL=... python scripts/restore_drill.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from db import connect

# Tables whose row counts must match exactly after restore. The corpus tables are the
# ones whose loss is catastrophic; the tenant tables are included so the whole public
# schema is proven, not just the easy half.
VERIFIED_TABLES = [
    "regulators", "instruments", "instrument_versions", "sections", "deltas",
    "crawl_runs", "organisations", "memberships", "watchlists", "control_mappings",
    "alerts", "usage_events", "llm_usage",
]


def counts(dsn: str) -> dict[str, int]:
    conn = connect(dsn)
    try:
        out: dict[str, int] = {}
        with conn.cursor() as cur:
            for table in VERIFIED_TABLES:
                try:
                    cur.execute(f"select count(*) from {table}")  # fixed identifiers
                    out[table] = cur.fetchone()[0]
                except Exception:  # noqa: BLE001 — a missing table is a real finding
                    conn.rollback()
                    out[table] = -1
        return out
    finally:
        conn.close()


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def prepare_target(dsn: str) -> None:
    """Wipe the restore target and lay down the stubs a public-only dump needs."""
    conn = connect(dsn)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("drop schema if exists public cascade")
            cur.execute("create schema public")
            # The public dump references the auth schema (auth.users FK, auth.uid() in
            # RLS policies). Stub both so the schema restores; the FK's data enforcement
            # is skipped by --disable-triggers during the data phase.
            cur.execute("create schema if not exists auth")
            cur.execute("create table if not exists auth.users (id uuid primary key)")
            cur.execute("create or replace function auth.uid() returns uuid "
                        "language sql stable as $$ select null::uuid $$")
            cur.execute("create extension if not exists pgcrypto")
            cur.execute("create extension if not exists pg_trgm")
    finally:
        conn.close()


def restore(dump_path: Path, dsn: str) -> None:
    prepare_target(dsn)
    # Schema first, then data with FK/triggers disabled. Errors are tolerated on the
    # schema phase (the pg_trgm/pgcrypto extensions already exist) but the data phase
    # must succeed.
    run(["pg_restore", "--no-owner", "--no-privileges",
         "--section=pre-data", "--section=post-data", "--dbname", dsn, str(dump_path)])
    run(["pg_restore", "--no-owner", "--no-privileges", "--data-only",
         "--disable-triggers", "--dbname", dsn, str(dump_path)])


def rls_intact(dsn: str) -> bool:
    """The one control an FI cares about must survive a restore, not just the data."""
    conn = connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("select count(*) from pg_policies where schemaname = 'public'")
            policies = cur.fetchone()[0]
            cur.execute("select 1 from pg_indexes where indexname = 'sections_body_trgm_idx'")
            trgm = cur.fetchone() is not None
        return policies > 0 and trgm
    finally:
        conn.close()


def main() -> int:
    source = os.environ.get("DATABASE_URL")
    target = os.environ.get("RESTORE_DATABASE_URL")
    if not source or not target:
        print("both DATABASE_URL and RESTORE_DATABASE_URL must be set")
        return 2

    print("1. capturing source row counts")
    source_counts = counts(source)

    print("2. dumping source")
    from backup import dump
    with tempfile.NamedTemporaryFile(suffix=".dump") as tmp:
        dump_path = Path(tmp.name)
        dump(source, dump_path)
        print(f"   dump: {dump_path.stat().st_size/1_000_000:.1f} MB")

        print("3. restoring into the isolated target")
        try:
            restore(dump_path, target)
        except subprocess.CalledProcessError as exc:
            print(f"RESTORE FAILED\nstdout:\n{exc.stdout}\nstderr:\n{exc.stderr}")
            return 1

    print("4. verifying row counts round-trip\n")
    restored_counts = counts(target)

    print(f"{'table':<22}{'source':>10}{'restored':>10}   status")
    mismatches = []
    for table in VERIFIED_TABLES:
        s, r = source_counts[table], restored_counts[table]
        ok = s == r
        if not ok:
            mismatches.append(table)
        print(f"{table:<22}{s:>10}{r:>10}   {'ok' if ok else 'MISMATCH'}")

    print()
    if not rls_intact(target):
        print("FAIL: RLS policies or the trigram index did not survive the restore.")
        return 1
    print("RLS policies and the trigram index restored.")

    if mismatches:
        print(f"\nRESTORE DRILL FAILED — row counts differ for: {', '.join(mismatches)}")
        return 1
    print("\nRESTORE DRILL PASSED — every table round-tripped, RLS intact. "
          "The backup is restorable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
