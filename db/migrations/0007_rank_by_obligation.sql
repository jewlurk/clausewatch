-- 0007 — order the console's changes by whether they alter an obligation, not by
-- severity alone.
--
-- Severity is a deterministic heuristic and cannot tell a substantive reword from a
-- mechanical one: a clause whose only change is a cross-reference following a
-- renumber (Notice 626 6.17 in the 2024 round, "6.16(f)" -> "6.16(d)") lands on the
-- same default 3 as a genuine amendment. The summariser's obligation_change flag is
-- the signal that separates them — it marks the change a compliance officer reads
-- first — so the console now sorts on it ahead of severity.
--
-- Mapped controls still lead everything (that is the whole point of a mapping), and
-- the most recent revision still leads within that. This only reorders within a
-- single (mapping, revision) group. Same rows, same cap, same org scope as 0005.

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
   order by cm.id nulls last, tv.issue_date desc,
            d.obligation_change desc, d.severity desc
   limit least(greatest(max_rows, 1), 500);
$$;

revoke all on function public.my_changes(int) from public, anon;
grant execute on function public.my_changes(int) to authenticated;
