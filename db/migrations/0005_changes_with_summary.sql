-- 0005 — my_changes returns the summary and the new clause text.
--
-- The console rendered "See the official text at MAS" for every ADDED clause, because
-- an added clause has no diff to show (there is no previous version to diff against)
-- and the function returned nothing else. Meanwhile MODIFIED changes dumped the whole
-- clause as an inline diff, which is the problem the summaries were written to solve.
--
-- So the function now returns the plain-language summary, the obligation flag, and the
-- new clause body. Still capped, still org-scoped: this widens what a caller sees about
-- a change they are already entitled to, not which changes they can see.

drop function if exists public.my_changes(int);

create function public.my_changes(max_rows int default 200)
returns table (
  delta_id bigint, instrument_ref text, source_url text,
  section_key text, op text, severity smallint, diff_html text,
  revision_date date, effective_date date,
  internal_ref text, mapping_id bigint,
  ai_summary text, obligation_change boolean, new_body text
)
language sql
security definer
set search_path = public
as $$
  select d.id, i.external_ref, i.source_url,
         coalesce(d.new_section_key, d.old_section_key),
         d.op, d.severity, d.diff_html,
         tv.issue_date, tv.effective_date,
         cm.internal_ref, cm.id,
         d.ai_summary, d.obligation_change,
         -- Excerpt, not the clause: enough to know what the change says without the
         -- response becoming a route to the full instrument (§11).
         left(ns.body, 600)
    from deltas d
    join instruments i on i.id = d.instrument_id
    join instrument_versions tv on tv.id = d.to_version_id
    left join sections ns on ns.id = d.new_section_id
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
