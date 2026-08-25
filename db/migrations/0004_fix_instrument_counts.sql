-- 0004 — fix inflated counts in list_instruments.
--
-- The original joined instrument_versions and deltas in the same query, so each
-- delta row was multiplied by the number of versions: Notice 626 reported 4,005
-- changes instead of 267. Counting through independent subqueries avoids the
-- fan-out.

create or replace function public.list_instruments()
returns table (
  id bigint, external_ref text, title text, source_url text,
  applies_to text[], latest_revision date, change_count bigint, version_count bigint
)
language sql
security definer
set search_path = public
as $$
  select i.id, i.external_ref, i.title, i.source_url, i.applies_to,
         (select max(v.issue_date) from instrument_versions v
           where v.instrument_id = i.id),
         (select count(*) from deltas d where d.instrument_id = i.id),
         (select count(*) from instrument_versions v where v.instrument_id = i.id)
    from instruments i
   order by i.external_ref;
$$;

revoke all on function public.list_instruments() from public;
grant execute on function public.list_instruments() to anon, authenticated;
