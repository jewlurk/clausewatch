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
        applies_to: tuple[str, ...] = (),
    ) -> int:
        """Return the instrument id, creating it if absent.

        Idempotent: the daily crawl re-sees the same instruments every run.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                insert into instruments
                    (regulator_id, external_ref, title, instrument_type, source_url,
                     applies_to)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (regulator_id, external_ref) do update
                    set title = excluded.title,
                        source_url = excluded.source_url,
                        applies_to = excluded.applies_to
                returning id
                """,
                (regulator_id, external_ref, title, instrument_type, source_url,
                 list(applies_to)),
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

    def delete_deltas_for_instrument(self, instrument_id: int) -> int:
        """Clear an instrument's deltas.

        Must run before re-parsing sections: deltas reference section ids, so deleting
        sections while deltas still point at them violates the foreign key. Ordering
        matters — deltas depend on sections, so deltas go first.
        """
        with self.conn.cursor() as cur:
            cur.execute("delete from deltas where instrument_id = %s", (instrument_id,))
            return cur.rowcount

    def replace_sections(self, version_id: int, sections) -> int:
        """Write a version's sections, replacing any previous parse.

        Replace rather than append: re-parsing after a parser improvement must not
        leave stale rows behind, and the parser is expected to keep improving.
        """
        with self.conn.cursor() as cur:
            cur.execute("delete from sections where version_id = %s", (version_id,))
            if not sections:
                return 0
            cur.executemany(
                """
                insert into sections
                    (version_id, section_key, depth, ordinal, heading, body, body_sha256)
                values (%s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        version_id,
                        s.section_key,
                        s.depth,
                        s.ordinal,
                        s.heading,
                        s.body,
                        s.body_sha256,
                    )
                    for s in sections
                ],
            )
            cur.execute(
                "update instrument_versions set parse_status = 'parsed', parse_error = null "
                "where id = %s",
                (version_id,),
            )
        return len(sections)

    def mark_parse_failed(self, version_id: int, error: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "update instrument_versions set parse_status = 'failed', parse_error = %s "
                "where id = %s",
                (error[:2000], version_id),
            )

    def section_ids(self, version_id: int) -> dict[str, int]:
        with self.conn.cursor() as cur:
            cur.execute(
                "select section_key, id from sections where version_id = %s",
                (version_id,),
            )
            return dict(cur.fetchall())

    def replace_deltas(
        self, *, instrument_id: int, from_version_id: int, to_version_id: int, deltas
    ) -> int:
        """Write the delta set for one version pair, replacing any previous computation.

        The unique index on (from, to, old_section, new_section) makes re-running safe,
        but thresholds change as the differ is tuned, so a stale delta must not survive
        a recomputation.
        """
        old_ids = self.section_ids(from_version_id)
        new_ids = self.section_ids(to_version_id)

        with self.conn.cursor() as cur:
            cur.execute(
                "delete from deltas where from_version_id = %s and to_version_id = %s",
                (from_version_id, to_version_id),
            )
            if not deltas:
                return 0
            cur.executemany(
                """
                insert into deltas
                    (instrument_id, from_version_id, to_version_id, op,
                     old_section_id, new_section_id, old_section_key, new_section_key,
                     similarity, diff_html, severity, obligation_change)
                values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        instrument_id,
                        from_version_id,
                        to_version_id,
                        d.op,
                        old_ids.get(d.old_section_key) if d.old_section_key else None,
                        new_ids.get(d.new_section_key) if d.new_section_key else None,
                        d.old_section_key,
                        d.new_section_key,
                        d.similarity,
                        d.diff_html,
                        d.severity,
                        d.obligation_change,
                    )
                    for d in deltas
                ],
            )
        return len(deltas)

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

    # ---------- crawl observability ----------

    def start_crawl_run(self, regulator_id: int) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                "insert into crawl_runs (regulator_id) values (%s) returning id",
                (regulator_id,),
            )
            return cur.fetchone()[0]

    def finish_crawl_run(
        self,
        run_id: int,
        *,
        status: str,
        docs_seen: int = 0,
        versions_new: int = 0,
        deltas_created: int = 0,
        error: str | None = None,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                update crawl_runs
                   set finished_at = now(), status = %s, docs_seen = %s,
                       versions_new = %s, deltas_created = %s, error = %s
                 where id = %s
                """,
                (status, docs_seen, versions_new, deltas_created,
                 (error or None) and error[:2000], run_id),
            )

    def last_successful_crawl(self):
        """When the corpus was last confirmed current.

        Drives the "last checked" line on the public site. In a month where nothing
        changed, that line is the entire value on display — it is the difference
        between "nothing happened" and "nobody looked".
        """
        with self.conn.cursor() as cur:
            cur.execute(
                "select finished_at from crawl_runs where status = 'ok' "
                "and finished_at is not null order by finished_at desc limit 1"
            )
            row = cur.fetchone()
        return row[0] if row else None

    # ---------- enrichment ----------

    def deltas_needing_summary(self, limit: int = 500) -> list[dict]:
        """Material changes that have no summary yet.

        Severity >= 3 only (§10), so cosmetic changes never reach a paid API call.
        Ordered newest-first: if the budget runs out, the changes a customer is most
        likely to be looking at are the ones that got summarised.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                select d.id, i.external_ref,
                       coalesce(d.new_section_key, d.old_section_key) as section_key,
                       os.body as old_body, ns.body as new_body
                  from deltas d
                  join instruments i on i.id = d.instrument_id
                  join instrument_versions tv on tv.id = d.to_version_id
                  left join sections os on os.id = d.old_section_id
                  left join sections ns on ns.id = d.new_section_id
                 where d.severity >= 3 and d.ai_summary is null
                 order by tv.issue_date desc nulls last, d.severity desc
                 limit %s
                """,
                (limit,),
            )
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    def save_summary(
        self, delta_id: int, *, summary: str, obligation_change: bool, action_hint: str
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "update deltas set ai_summary = %s, obligation_change = %s, "
                "ai_action_hint = %s where id = %s",
                (summary, obligation_change, action_hint or None, delta_id),
            )
