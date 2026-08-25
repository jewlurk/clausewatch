-- 0003_tenant_app.sql — the customer-facing layer.
--
-- Design note. The corpus tables are locked to anon and authenticated (migration
-- 0002), and they stay locked. A signed-in customer must never be able to SELECT
-- freely from `sections` or `deltas`: that is how an instrument's full text would
-- leak, which §11 forbids and §4.3 makes a legal problem rather than a product one.
--
-- So all corpus reads go through `security definer` functions below. They run with
-- the owner's rights, join only what the caller is entitled to via their org, and cap
-- the number of rows returned. The cap lives in the database, not in application code,
-- because the database is the only layer a customer cannot route around.

-- ---------- signup: every user gets an organisation ----------

create or replace function public.bootstrap_org(org_name text, entity_type text default null)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  new_org uuid;
begin
  if auth.uid() is null then
    raise exception 'not authenticated';
  end if;

  -- One org per user for now. A second call returns the existing org rather than
  -- silently creating a duplicate the user can never see.
  select m.org_id into new_org from memberships m where m.user_id = auth.uid() limit 1;
  if new_org is not null then
    return new_org;
  end if;

  insert into organisations (name, entity_type)
  values (coalesce(nullif(trim(org_name), ''), 'My organisation'), entity_type)
  returning id into new_org;

  insert into memberships (user_id, org_id, role) values (auth.uid(), new_org, 'owner');

  insert into usage_events (org_id, user_id, event_type, metadata)
  values (new_org, auth.uid(), 'signup', jsonb_build_object('entity_type', entity_type));

  return new_org;
end;
$$;

revoke all on function public.bootstrap_org(text, text) from public, anon;
grant execute on function public.bootstrap_org(text, text) to authenticated;

-- ---------- corpus reads, capped ----------

-- The instrument list is metadata only: no clause text, so it is safe to expose whole.
create or replace function public.list_instruments()
returns table (
  id bigint, external_ref text, title text, source_url text,
  applies_to text[], latest_revision date, change_count bigint
)
language sql
security definer
set search_path = public
as $$
  select i.id, i.external_ref, i.title, i.source_url, i.applies_to,
         max(v.issue_date) as latest_revision,
         count(d.id) as change_count
    from instruments i
    left join instrument_versions v on v.instrument_id = i.id
    left join deltas d on d.instrument_id = i.id
   group by i.id
   order by i.external_ref;
$$;

revoke all on function public.list_instruments() from public;
grant execute on function public.list_instruments() to anon, authenticated;

-- Changes for the caller's organisation. Returns only clauses the org has either
-- watchlisted or mapped a control to, and never more than `max_rows`.
create or replace function public.my_changes(max_rows int default 200)
returns table (
  delta_id bigint, instrument_ref text, source_url text,
  section_key text, op text, severity smallint, diff_html text,
  revision_date date, effective_date date,
  internal_ref text, mapping_id bigint
)
language sql
security definer
set search_path = public
as $$
  select d.id, i.external_ref, i.source_url,
         coalesce(d.new_section_key, d.old_section_key),
         d.op, d.severity, d.diff_html,
         tv.issue_date, tv.effective_date,
         cm.internal_ref, cm.id
    from deltas d
    join instruments i on i.id = d.instrument_id
    join instrument_versions tv on tv.id = d.to_version_id
    join memberships m on m.user_id = auth.uid()
    left join control_mappings cm
           on cm.org_id = m.org_id
          and cm.instrument_id = d.instrument_id
          and cm.section_key = coalesce(d.new_section_key, d.old_section_key)
    left join watchlists w
           on w.org_id = m.org_id
          and (w.instrument_id = d.instrument_id
               or (w.applies_to is not null and w.applies_to = any(i.applies_to)))
   where (cm.id is not null or w.id is not null)
     and d.severity >= coalesce(w.min_severity, 2)
   order by cm.id nulls last, tv.issue_date desc, d.severity desc
   limit least(greatest(max_rows, 1), 500);
$$;

revoke all on function public.my_changes(int) from public, anon;
grant execute on function public.my_changes(int) to authenticated;

-- Clause numbers for the mapping UI's autocomplete. Keys only, never bodies —
-- a clause number is not protected text, the clause body is.
create or replace function public.clause_keys(p_instrument_id bigint)
returns table (section_key text)
language sql
security definer
set search_path = public
as $$
  select distinct s.section_key
    from sections s
    join instrument_versions v on v.id = s.version_id
   where v.instrument_id = p_instrument_id
     and v.id = (select id from instrument_versions
                  where instrument_id = p_instrument_id
                  order by issue_date desc nulls last limit 1)
   order by 1;
$$;

revoke all on function public.clause_keys(bigint) from public, anon;
grant execute on function public.clause_keys(bigint) to authenticated;

-- ---------- policies the app needs beyond 0001 ----------

-- 0001 gave organisations a SELECT policy only; bootstrap_org inserts as definer, so
-- no insert policy is needed. Members may rename their own org.
create policy org_update on organisations for update
  using (id in (select org_id from memberships where user_id = auth.uid()));

-- ---------- alert generation ----------

-- Called by the pipeline after deltas are computed. Creates one alert per
-- (org, delta, mapping); the unique index on alerts makes re-running a no-op.
create or replace function public.generate_alerts()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  created integer;
begin
  insert into alerts (org_id, delta_id, mapping_id)
  select distinct cm.org_id, d.id, cm.id
    from control_mappings cm
    join deltas d
      on d.instrument_id = cm.instrument_id
     and coalesce(d.new_section_key, d.old_section_key) = cm.section_key
   where d.severity >= 2
  on conflict (org_id, delta_id, mapping_id) do nothing;
  get diagnostics created = row_count;

  insert into alerts (org_id, delta_id, mapping_id)
  select distinct w.org_id, d.id, null
    from watchlists w
    join instruments i on (w.instrument_id = i.id
           or (w.applies_to is not null and w.applies_to = any(i.applies_to)))
    join deltas d on d.instrument_id = i.id
   where d.severity >= w.min_severity
  on conflict (org_id, delta_id, mapping_id) do nothing;

  return created;
end;
$$;

revoke all on function public.generate_alerts() from public, anon, authenticated;
