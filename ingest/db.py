"""Postgres persistence.

Connects through Supabase's connection pooler. Direct connections are IPv6-only on
the free tier and GitHub Actions runners have no IPv6, so the pooler is not a
preference — it is the only route that works from CI.

`prepare_threshold=None` disables prepared statements. The session pooler supports
them and the transaction pooler does not, so disabling makes the code correct against
either, and the query volume here is far too low for prepared statements to matter.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg


def connect(dsn: str | None = None) -> psycopg.Connection:
    dsn = dsn or os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg.connect(dsn, prepare_threshold=None, autocommit=False)


@contextmanager
def connection(dsn: str | None = None):
    conn = connect(dsn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class PostgresVersionRepository:
    """instrument_versions persistence, matching the VersionRepository protocol."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    # ---------- corpus lookups ----------

    def regulator_id(self, code: str) -> int:
        with self.conn.cursor() as cur:
            cur.execute("select id from regulators where code = %s", (code,))
            row = cur.fetchone()
        if row is None:
            raise LookupError(f"regulator {code!r} not seeded")
        return row[0]

    def upsert_instrument(
        self,
        *,
        regulator_id: int,
        external_ref: str,
        title: str,
        instrument_type: str,
        source_url: str,
    ) -> int:
        """Return the instrument id, creating it if absent.

        Idempotent: the daily crawl re-sees the same instruments every run.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                insert into instruments
                    (regulator_id, external_ref, title, instrument_type, source_url)
                values (%s, %s, %s, %s, %s)
                on conflict (regulator_id, external_ref) do update
                    set title = excluded.title,
                        source_url = excluded.source_url
                returning id
                """,
                (regulator_id, external_ref, title, instrument_type, source_url),
            )
            return cur.fetchone()[0]

    # ---------- VersionRepository protocol ----------

    def version_exists(self, instrument_id: int, content_sha256: str) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                "select 1 from instrument_versions "
                "where instrument_id = %s and content_sha256 = %s",
                (instrument_id, content_sha256),
            )
            return cur.fetchone() is not None

    def insert_version(
        self, *, instrument_id: int, content_sha256: str, r2_key: str, mime_type: str
    ) -> int:
        """Insert a version, or return the existing id if the content is already known.

        The on-conflict clause makes concurrent or repeated runs safe: the unique
        index on (instrument_id, content_sha256) is the real dedup guarantee, and this
        method must never raise just because the crawler ran twice.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                insert into instrument_versions
                    (instrument_id, content_sha256, r2_key, mime_type)
                values (%s, %s, %s, %s)
                on conflict (instrument_id, content_sha256) do update
                    set r2_key = excluded.r2_key
                returning id
                """,
                (instrument_id, content_sha256, r2_key, mime_type),
            )
            return cur.fetchone()[0]

    def set_version_dates(
        self, version_id: int, issue_date=None, effective_date=None
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "update instrument_versions set issue_date = %s, effective_date = %s "
                "where id = %s",
                (issue_date, effective_date, version_id),
            )

    def versions_for(self, instrument_id: int) -> list[dict]:
        with self.conn.cursor() as cur:
            cur.execute(
                "select id, content_sha256, r2_key, issue_date, fetched_at "
                "from instrument_versions where instrument_id = %s "
                "order by fetched_at",
                (instrument_id,),
            )
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
