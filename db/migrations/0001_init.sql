-- 0001_init.sql — initial schema. Source of truth: CLAUDE.md §8.
-- Forward-only. Never edit this file after it has been applied; add 0002_*.sql instead.

create extension if not exists pg_trgm;
create extension if not exists pgcrypto;

-- ---------- Corpus (public data) ----------

create table regulators (
  id           smallserial primary key,
  code         text not null unique,          -- 'MAS','ACRA','IRAS','SGX','CEA'
  name         text not null,
  base_url     text not null
);

create table instruments (
  id              bigserial primary key,
  regulator_id    smallint not null references regulators(id),
  external_ref    text not null,              -- 'Notice 626','PSN02','SFA04-N02'
  title           text not null,
  instrument_type text not null,              -- notice|guideline|circular|faq|code|practice_note
  source_url      text not null,
  applies_to      text[] default '{}',        -- ['bank','payment_institution','lfmc']
  is_active       boolean not null default true,
  first_seen_at   timestamptz not null default now(),
  unique (regulator_id, external_ref)
);
create index on instruments using gin (applies_to);

create table instrument_versions (
  id             bigserial primary key,
  instrument_id  bigint not null references instruments(id) on delete cascade,
  content_sha256 char(64) not null,
  r2_key         text not null,
  mime_type      text not null,
  issue_date     date,
  effective_date date,                        -- often differs; drives alert urgency
  fetched_at     timestamptz not null default now(),
  parse_status   text not null default 'pending',   -- pending|parsed|failed
  parse_error    text,
  unique (instrument_id, content_sha256)
);
create index on instrument_versions (instrument_id, fetched_at desc);

create table sections (
  id              bigserial primary key,
  version_id      bigint not null references instrument_versions(id) on delete cascade,
  section_key     text not null,              -- normalised clause number: '6.14.2'
  depth           smallint not null,
  ordinal         integer not null,
  heading         text,
  body            text not null,
  body_sha256     char(64) not null,
  unique (version_id, section_key)
);
create index on sections (version_id, ordinal);
-- Load-bearing: this is how renumbering is solved without embeddings or LLM calls.
create index sections_body_trgm_idx on sections using gin (body gin_trgm_ops);

-- Computed change records. This table IS the product.
create table deltas (
  id                bigserial primary key,
  instrument_id     bigint not null references instruments(id) on delete cascade,
  from_version_id   bigint not null references instrument_versions(id),
  to_version_id     bigint not null references instrument_versions(id),
  op                text not null,            -- ADDED|REMOVED|MODIFIED|RENUMBERED
  old_section_id    bigint references sections(id),
  new_section_id    bigint references sections(id),
  old_section_key   text,
  new_section_key   text,
  similarity        real,
  diff_html         text,
  severity          smallint not null default 3,   -- 1 cosmetic .. 5 new obligation
  ai_summary        text,
  ai_action_hint    text,
  obligation_change boolean not null default false,
  created_at        timestamptz not null default now()
);
create index on deltas (instrument_id, created_at desc);
create index on deltas (to_version_id, severity desc);
create unique index on deltas (from_version_id, to_version_id,
                               coalesce(old_section_id,0), coalesce(new_section_id,0));

-- ---------- Tenant side (RLS enforced) ----------

create table organisations (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  plan        text not null default 'design_partner',
  entity_type text,
  created_at  timestamptz not null default now()
);

create table memberships (
  user_id uuid not null references auth.users(id) on delete cascade,
  org_id  uuid not null references organisations(id) on delete cascade,
  role    text not null default 'member',
  primary key (user_id, org_id)
);

create table watchlists (
  id            bigserial primary key,
  org_id        uuid not null references organisations(id) on delete cascade,
  instrument_id bigint references instruments(id) on delete cascade,
  applies_to    text,
  min_severity  smallint not null default 2,
  check (instrument_id is not null or applies_to is not null),
  unique (org_id, instrument_id, applies_to)
);

-- THE MOAT. 200 mapped controls = switching cost measured in months.
create table control_mappings (
  id              bigserial primary key,
  org_id          uuid not null references organisations(id) on delete cascade,
  instrument_id   bigint not null references instruments(id),
  section_key     text not null,
  internal_ref    text not null,              -- 'AML-POL-4.2','SOP-Onboarding-11'
  owner_email     text,
  notes           text,
  unique (org_id, instrument_id, section_key, internal_ref)
);
create index on control_mappings (instrument_id, section_key);

create table alerts (
  id              bigserial primary key,
  org_id          uuid not null references organisations(id) on delete cascade,
  delta_id        bigint not null references deltas(id) on delete cascade,
  mapping_id      bigint references control_mappings(id) on delete set null,
  status          text not null default 'open',   -- open|acknowledged|actioned|dismissed
  assigned_to     text,
  resolved_at     timestamptz,
  resolution_note text,
  created_at      timestamptz not null default now(),
  unique (org_id, delta_id, mapping_id)
);
create index on alerts (org_id, status, created_at desc);

-- Conversion evidence. Who is actually using this in March 2027?
create table usage_events (
  id         bigserial primary key,
  org_id     uuid references organisations(id) on delete cascade,
  user_id    uuid,
  event_type text not null,      -- login|alert_viewed|alert_actioned|mapping_created|export
  metadata   jsonb default '{}',
  created_at timestamptz not null default now()
);
create index on usage_events (org_id, created_at desc);
create index on usage_events (event_type, created_at desc);

create table crawl_runs (
  id             bigserial primary key,
  regulator_id   smallint not null references regulators(id),
  started_at     timestamptz not null default now(),
  finished_at    timestamptz,
  docs_seen      integer default 0,
  versions_new   integer default 0,
  deltas_created integer default 0,
  status         text not null default 'running',
  error          text
);

-- ---------- Row Level Security ----------

alter table organisations    enable row level security;
alter table memberships      enable row level security;
alter table watchlists       enable row level security;
alter table control_mappings enable row level security;
alter table alerts           enable row level security;
alter table usage_events     enable row level security;

-- Direct (non-recursive) predicate. Every other policy below subqueries memberships,
-- so this policy must not itself reference memberships or the planner recurses.
create policy memberships_self on memberships for all
  using (user_id = auth.uid());

create policy org_read on organisations for select
  using (id in (select org_id from memberships where user_id = auth.uid()));

create policy alerts_rw on alerts for all
  using (org_id in (select org_id from memberships where user_id = auth.uid()));

create policy watchlists_rw on watchlists for all
  using (org_id in (select org_id from memberships where user_id = auth.uid()));

create policy control_mappings_rw on control_mappings for all
  using (org_id in (select org_id from memberships where user_id = auth.uid()));

create policy usage_events_rw on usage_events for all
  using (org_id in (select org_id from memberships where user_id = auth.uid()));

-- Corpus tables (regulators, instruments, instrument_versions, sections, deltas,
-- crawl_runs) carry no RLS: the corpus is public data and is served through the API,
-- which enforces the §11 excerpt cap. No tenant data lives in them.

-- ---------- Seed ----------

insert into regulators (code, name, base_url)
values ('MAS', 'Monetary Authority of Singapore', 'https://www.mas.gov.sg')
on conflict (code) do nothing;
