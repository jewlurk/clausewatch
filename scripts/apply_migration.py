"""Apply a numbered migration.

Migrations are forward-only and are normally run by hand in the Supabase SQL editor.
This exists so a migration can also be applied from CI, where DATABASE_URL lives, and
so applying one is reproducible rather than a remembered sequence of clicks.

Deliberately dumb: it executes the file and reports. It keeps no migration ledger —
with a handful of numbered files, a tracking table would be more machinery than the
problem deserves.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from db import connection

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: apply_migration.py <name, e.g. 0003_tenant_app>")
        return 2
    path = ROOT / "db" / "migrations" / f"{sys.argv[1]}.sql"
    if not path.exists():
        print(f"FAIL: {path} not found")
        return 1

    sql = path.read_text()
    print(f"applying {path.name} ({len(sql)} bytes)")
    with connection() as conn, conn.cursor() as cur:
        cur.execute(sql)
    print("applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
