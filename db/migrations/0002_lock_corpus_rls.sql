-- 0002_lock_corpus_rls.sql
--
-- SECURITY FIX. 0001 left the corpus tables without row level security, on the
-- reasoning that they hold public data. Verified against the live project on
-- 2026-08-25, that reasoning was wrong on two counts:
--
--   1. Supabase grants the anon role full DML on public-schema tables; RLS is what
--      withholds it. With RLS off, the publishable key — which is public by design and
--      committed to a public repo — could INSERT, UPDATE and DELETE the corpus.
--      Probed: INSERT reached the NOT NULL check (23502) instead of being refused, and
--      DELETE returned 204.
--   2. Anon could SELECT whole rows from `sections` and `deltas`, which carry full
--      clause text. PostgREST bypasses our API, so the §11 excerpt cap could not
--      apply, and serving the corpus in bulk is what §4.3 forbids.
--
-- Fix: enable RLS on every corpus table and grant no policy to anon or authenticated.
-- Nothing is readable or writable through PostgREST. The crawler and the Hono Worker
-- both use the secret/service key server-side, which bypasses RLS, and the Worker
-- remains the only public read path so the §11 cap is always enforced.

alter table regulators          enable row level security;
alter table instruments         enable row level security;
alter table instrument_versions enable row level security;
alter table sections            enable row level security;
alter table deltas              enable row level security;
alter table crawl_runs          enable row level security;

-- Deliberately no policies: with RLS enabled and no policy, anon and authenticated
-- get nothing. Do not add a broad "read all" policy to these tables — an endpoint that
-- returns an instrument's full text is the one thing §11 forbids outright.

-- Belt and braces: withdraw the table-level grants too, so a future migration that
-- adds a permissive policy cannot silently reopen write access.
revoke insert, update, delete on
  regulators, instruments, instrument_versions, sections, deltas, crawl_runs
  from anon, authenticated;
