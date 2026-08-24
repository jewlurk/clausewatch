"""Verify R2 credentials and bucket access end to end.

Run from GitHub Actions (where the secrets live) via the crawl workflow's
workflow_dispatch trigger. Writes one small object, reads it back, and reports.

Exists because the credentials are only available in CI, so there is otherwise no
way to know they are correct until the crawler fails at 09:17 SGT.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from store import R2Store

PROBE_KEY = "_healthcheck/r2-connectivity.txt"


def main() -> int:
    missing = [
        name
        for name in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
        if not os.environ.get(name)
    ]
    if missing:
        print(f"FAIL: missing environment variables: {', '.join(missing)}")
        return 1

    print(f"bucket   : {os.environ['R2_BUCKET']}")
    print(f"endpoint : https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com")

    try:
        store = R2Store()
        store.put(PROBE_KEY, b"clausewatch r2 connectivity check\n", "text/plain")
        print("write    : OK")
        if not store.exists(PROBE_KEY):
            print("FAIL: object written but not found on read-back")
            return 1
        print("read     : OK")
    except Exception as exc:  # noqa: BLE001 - report any failure plainly
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1

    print("\nR2 credentials and bucket access are working.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
