"""Backup retention (backup.py, T32).

The dump-and-upload itself needs a live database and R2, so it is proven in CI by the
restore drill. What is unit-testable here is the pruning rule — the one piece of logic
that could delete the wrong thing.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import backup


class FakeStore:
    def __init__(self, keys):
        self.keys = list(keys)
        self.deleted = []

    def list_keys(self, prefix=""):
        return [k for k in self.keys if k.startswith(prefix)]

    def delete(self, key):
        self.deleted.append(key)
        self.keys.remove(key)


def dated(n):
    return [f"backups/clausewatch-2026{m:02d}01T000000Z.dump" for m in range(1, n + 1)]


def test_keeps_the_most_recent_and_deletes_the_rest():
    store = FakeStore(dated(backup.KEEP + 3))
    removed = backup.prune(store)
    assert len(removed) == 3
    # The three deleted are the oldest (lexicographically smallest dated keys).
    assert removed == sorted(dated(backup.KEEP + 3))[:3]
    assert len(store.keys) == backup.KEEP


def test_nothing_deleted_when_under_the_limit():
    store = FakeStore(dated(backup.KEEP))
    assert backup.prune(store) == []
    assert len(store.keys) == backup.KEEP


def test_prune_ignores_non_dump_objects_in_the_prefix():
    store = FakeStore(["backups/README.txt", *dated(backup.KEEP + 1)])
    removed = backup.prune(store)
    assert len(removed) == 1
    assert "backups/README.txt" not in store.deleted


def test_prune_only_touches_the_backups_prefix():
    store = FakeStore(["MAS/notice-626/abc.pdf", *dated(backup.KEEP + 2)])
    backup.prune(store)
    assert "MAS/notice-626/abc.pdf" not in store.deleted
