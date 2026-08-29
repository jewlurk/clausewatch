"""Offsite logical backup (T32, brief §32).

Supabase's free tier gives no point-in-time recovery, so the backup we control is a
logical dump we take ourselves and store in R2 — a different provider, in our own
bucket. The corpus is the company: 15 years of MAS history reconstructed clause by
clause. Losing it is not "restore from a snapshot", it is re-running every backfill and
re-tuning the differ. This makes that unnecessary.

Dumps the `public` schema (the whole corpus and the tenant tables) in pg_dump's custom
format, uploads it to R2 under a dated key, and prunes to the most recent KEEP backups.
Restorability is proved separately by scripts/restore_drill.py — a dump nobody has ever
restored is a belief, not a backup.

    DATABASE_URL=... python scripts/backup.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from store import R2Store

KEEP = 8  # weekly backups retained; ~two months of history
PREFIX = "backups/"


def dump(database_url: str, out_path: Path) -> None:
    # --no-owner / --no-privileges: the dump restores onto any Postgres without needing
    # Supabase's role model. Custom format so pg_restore can load schema and data in
    # separate phases (the restore drill needs that to bypass the auth.users FK).
    subprocess.run(
        ["pg_dump", "--format=custom", "--no-owner", "--no-privileges",
         "--schema=public", "--file", str(out_path), database_url],
        check=True,
    )


def prune(store: R2Store) -> list[str]:
    """Delete all but the most recent KEEP dated backups. Returns the keys removed."""
    keys = sorted(k for k in store.list_keys(PREFIX) if k.endswith(".dump"))
    stale = keys[:-KEEP] if len(keys) > KEEP else []
    for key in stale:
        store.delete(key)
    return stale


def main() -> int:
    import os
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set")
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"{PREFIX}clausewatch-{stamp}.dump"

    with tempfile.NamedTemporaryFile(suffix=".dump") as tmp:
        out = Path(tmp.name)
        dump(database_url, out)
        size = out.stat().st_size
        store = R2Store()
        store.put(key, out.read_bytes(), "application/octet-stream")

    print(f"backup uploaded: {key} ({size/1_000_000:.1f} MB)")
    removed = prune(store)
    if removed:
        print(f"pruned {len(removed)} old backup(s): {', '.join(removed)}")
    print(f"retaining the most recent {KEEP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
