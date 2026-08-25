-- 0006 — make alert generation actually work, and give T26 something to send from.
--
-- Three defects, all found by scripts/verify_console.py running against the live
-- database. None had ever surfaced because nothing in the pipeline called
-- generate_alerts(), so the alerts table has been empty since it was created.
--
--   1. generate_alerts() raised on every call. The watchlist branch selects a bare
--      `null` into `mapping_id`; inside SELECT DISTINCT, Postgres resolves an untyped
--      NULL as `text`, and the insert failed with
--      "column mapping_id is of type bigint but expression is of type text".
--      Because it is a plpgsql function, the mapped-control insert that runs first was
--      rolled back with it. Net effect: zero alerts, ever.
--
--   2. Even with the cast, `on conflict (org_id, delta_id, mapping_id) do nothing`
--      cannot deduplicate the watchlist rows, because those carry mapping_id = null
--      and a unique index treats NULLs as distinct by default. Every run would have
--      inserted the whole watchlist backlog again. The constraint is rebuilt as a
--      unique index with NULLS NOT DISTINCT (Postgres 15+; this project is on 17.6).
--
--   3. There was nothing recording that an alert had been emailed, so a mail job had
--      no way to avoid sending the same change every night. `notified_at` fixes that.

-- ---------- 3. delivery state ----------

alter table alerts add column if not exists notified_at timestamptz;

-- Partial index: the mailer only ever asks for the unsent ones.
create index if not exists alerts_unnotified_idx
  on alerts (org_id, created_at) where notified_at is null;

-- ---------- 2. a uniqueness rule that survives a null mapping_id ----------

do $$
declare
  conname text;
begin
  select c.conname into conname
    from pg_constraint c
   where c.conrelid = 'public.alerts'::regclass
     and c.contype = 'u'
     and (select array_agg(a.attname::text order by a.attname)
            from unnest(c.conkey) k
            join pg_attribute a on a.attrelid = c.conrelid and a.attnum = k)
         = array['delta_id','mapping_id','org_id'];
  if conname is not null then
    execute format('alter table alerts drop constraint %I', conname);
  end if;
end $$;

drop index if exists alerts_dedup_idx;
create unique index alerts_dedup_idx
  on alerts (org_id, delta_id, mapping_id) nulls not distinct;

-- ---------- 1. the function itself ----------

create or replace function public.generate_alerts()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  created integer := 0;
  n       integer;
begin
  -- Mapped controls first. These are the alerts that name the customer's own internal
  -- reference, and they are the reason anyone renews.
  insert into alerts (org_id, delta_id, mapping_id)
  select distinct cm.org_id, d.id, cm.id
    from control_mappings cm
    join deltas d
      on d.instrument_id = cm.instrument_id
     and coalesce(d.new_section_key, d.old_section_key) = cm.section_key
   where d.severity >= 2
  on conflict (org_id, delta_id, mapping_id) do nothing;
  get diagnostics n = row_count;
  created := created + n;

  -- Watchlist hits, excluding any delta the org already has a mapped alert for: one
  -- change must not produce two emails to the same reader.
  insert into alerts (org_id, delta_id, mapping_id)
  select distinct w.org_id, d.id, null::bigint
    from watchlists w
    join instruments i on (w.instrument_id = i.id
           or (w.applies_to is not null and w.applies_to = any(i.applies_to)))
    join deltas d on d.instrument_id = i.id
   where d.severity >= w.min_severity
     and not exists (select 1 from alerts a
                      where a.org_id = w.org_id and a.delta_id = d.id)
  on conflict (org_id, delta_id, mapping_id) do nothing;
  get diagnostics n = row_count;
  created := created + n;

  return created;
end;
$$;

revoke all on function public.generate_alerts() from public, anon, authenticated;

-- ---------- what the mailer reads ----------

-- One row per alert that still needs sending, with everything an email needs and
-- nothing it does not. Owner-only: the pipeline calls this with the service
-- credential, never the browser.
create or replace function public.pending_alerts(max_rows int default 500)
returns table (
  alert_id bigint, org_id uuid, org_name text, recipient text,
  instrument_ref text, instrument_title text, source_url text,
  section_key text, op text, severity smallint,
  revision_date date, effective_date date,
  internal_ref text, ai_summary text, obligation_change boolean
)
language sql
security definer
set search_path = public
as $$
  select a.id, o.id, o.name, u.email::text,
         i.external_ref, i.title, i.source_url,
         coalesce(d.new_section_key, d.old_section_key),
         d.op, d.severity, tv.issue_date, tv.effective_date,
         cm.internal_ref, d.ai_summary, d.obligation_change
    from alerts a
    join organisations o on o.id = a.org_id
    join deltas d on d.id = a.delta_id
    join instruments i on i.id = d.instrument_id
    join instrument_versions tv on tv.id = d.to_version_id
    join memberships m on m.org_id = a.org_id
    join auth.users u on u.id = m.user_id
    left join control_mappings cm on cm.id = a.mapping_id
   where a.notified_at is null
     and u.email is not null
   order by a.org_id, cm.id nulls last, d.severity desc, a.id
   limit least(greatest(max_rows, 1), 2000);
$$;

revoke all on function public.pending_alerts(int) from public, anon, authenticated;
