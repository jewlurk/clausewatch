-- 0008 — persist LLM token usage per enrichment run (T29, §13).
--
-- §13: "Log token counts per call. We cannot manage a budget we don't measure." Until
-- now the per-run totals were printed to the Actions log and lost when the log rotated,
-- so there was no way to answer "how many tokens this month" without scraping CI logs.
-- This records one row per enrichment run, which is all the weekly cost report needs to
-- sum a month's spend and estimate the bill.
--
-- Corpus-side table (no org_id), so it lives with RLS enabled and no policy like the
-- rest of the corpus — the pipeline writes it with the service credential, and neither
-- anon nor authenticated can read it. Token counts are operational data, not customer
-- data; nothing here is org-scoped.

create table if not exists llm_usage (
  id             bigserial primary key,
  model          text not null,
  calls          integer not null default 0,
  input_tokens   bigint not null default 0,
  output_tokens  bigint not null default 0,
  rejected       integer not null default 0,
  summarised     integer not null default 0,
  created_at     timestamptz not null default now()
);
create index if not exists llm_usage_created_idx on llm_usage (created_at desc);

alter table llm_usage enable row level security;
-- Deliberately no policy: closed to anon and authenticated, same as every corpus table.
revoke insert, update, delete on llm_usage from anon, authenticated;
