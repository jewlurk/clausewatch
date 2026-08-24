"""Verify DATABASE_URL works and the schema is present.

Run from GitHub Actions, where the secret lives. Reports the specific failure rather
than a generic timeout, because the two likely mistakes — using the direct connection
instead of the pooler, and a wrong pooler hostname — both surface as connection
timeouts that look like firewall problems.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from db import PostgresVersionRepository, connect

EXPECTED_TABLES = [
    "regulators",
    "instruments",
    "instrument_versions",
    "sections",
    "deltas",
    "crawl_runs",
]


def describe_dsn(dsn: str) -> None:
    """Print the shape of the DSN without revealing the password."""
    parts = urlsplit(dsn)
    user = (parts.username or "?")
    host = parts.hostname or "?"
    print(f"user : {user}")
    print(f"host : {host}")
    print(f"port : {parts.port}")
    if "pooler.supabase.com" not in host:
        print(
            "\nWARNING: host is not the pooler. Supabase direct connections are "
            "IPv6-only and GitHub Actions has no IPv6 — this will time out."
        )


def main() -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("FAIL: DATABASE_URL is not set")
        return 1

    describe_dsn(dsn)

    try:
        conn = connect(dsn)
    except Exception as exc:  # noqa: BLE001
        print(f"\nFAIL: could not connect: {type(exc).__name__}: {exc}")
        print(
            "\nMost likely causes:\n"
            "  1. Using the direct connection instead of the session pooler\n"
            "  2. Wrong pooler hostname (aws-0 vs aws-1) — check the Connect panel\n"
            "  3. Password not substituted, or special characters not percent-encoded"
        )
        return 1

    with conn:
        with conn.cursor() as cur:
            cur.execute("select version()")
            print(f"\nconnected: {cur.fetchone()[0].split(',')[0]}")

            cur.execute(
                "select table_name from information_schema.tables "
                "where table_schema = 'public'"
            )
            present = {r[0] for r in cur.fetchall()}

        missing = [t for t in EXPECTED_TABLES if t not in present]
        if missing:
            print(f"FAIL: missing tables: {', '.join(missing)} — run the migrations")
            return 1
        print(f"schema   : all {len(EXPECTED_TABLES)} corpus tables present")

        repo = PostgresVersionRepository(conn)
        print(f"regulator: MAS id={repo.regulator_id('MAS')}")

    print("\nDATABASE_URL works and the schema is in place.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
