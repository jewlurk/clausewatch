"""Generate the public changelog demo page (T21 / gate G2).

Reads the corpus from Postgres and emits a single static HTML file. No framework, no
CSS library, one stylesheet — brief §4.2. Credibility comes from typography and from
the data being correct, not from dependencies.

§11 guard, enforced here rather than trusted: a comparison may display at most
EXCERPT_CAP of an instrument's clauses. The 2014->2015 restatement changed more
clauses than the document contains, so rendering every delta would effectively
republish the instrument, which §4.3 forbids. Anything above the cap is summarised and
deep-linked to MAS instead.
"""
from __future__ import annotations

import html
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from db import connection

INSTRUMENT_REF = "Notice 626"
OUT = Path(__file__).resolve().parent.parent / "web" / "index.html"

# Never display more than this share of an instrument's clauses in one comparison.
EXCERPT_CAP = 0.40

OP_LABEL = {
    "ADDED": "Added",
    "REMOVED": "Removed",
    "MODIFIED": "Modified",
    "RENUMBERED": "Renumbered",
}


def fetch(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            select i.id, i.external_ref, i.title, i.source_url
            from instruments i
            join regulators r on r.id = i.regulator_id
            where r.code = 'MAS' and i.external_ref = %s
            """,
            (INSTRUMENT_REF,),
        )
        instrument = cur.fetchone()
        if instrument is None:
            raise SystemExit(f"instrument {INSTRUMENT_REF!r} not found")
        instrument_id = instrument[0]

        cur.execute(
            """
            select d.from_version_id, d.to_version_id,
                   fv.issue_date, tv.issue_date, tv.effective_date,
                   d.op, d.new_section_key, d.old_section_key,
                   d.severity, d.diff_html, d.similarity
            from deltas d
            join instrument_versions fv on fv.id = d.from_version_id
            join instrument_versions tv on tv.id = d.to_version_id
            where d.instrument_id = %s
            order by tv.issue_date desc, d.severity desc, d.new_section_key
            """,
            (instrument_id,),
        )
        deltas = cur.fetchall()

        cur.execute(
            "select version_id, count(*) from sections group by version_id"
        )
        counts = dict(cur.fetchall())
    return instrument, deltas, counts


def group(deltas):
    out: dict[tuple, list] = {}
    for row in deltas:
        key = (row[0], row[1], row[2], row[3], row[4])
        out.setdefault(key, []).append(row[5:])
    return out


def sev_class(severity: int) -> str:
    return "high" if severity >= 4 else "med" if severity == 3 else "low"


def render(instrument, grouped, counts) -> str:
    _, ref, title, source_url = instrument
    comparisons = []

    for (from_id, to_id, from_date, to_date, effective), rows in grouped.items():
        clause_total = counts.get(to_id, 0) or 1
        cap = max(1, int(clause_total * EXCERPT_CAP))
        shown, hidden = rows[:cap], max(0, len(rows) - cap)

        items = []
        for op, new_key, old_key, severity, diff_html_text, similarity in shown:
            key = new_key or old_key or "—"
            moved = (
                f'<span class="moved">was {html.escape(old_key)}</span>'
                if op == "RENUMBERED" and old_key and old_key != new_key
                else ""
            )
            body = diff_html_text or (
                '<span class="muted">Clause added — see the official text at MAS.</span>'
                if op == "ADDED"
                else '<span class="muted">Clause removed.</span>'
                if op == "REMOVED"
                else '<span class="muted">Clause number changed; text unchanged.</span>'
            )
            sim = (
                f'<span class="sim">{similarity:.0%} similar</span>'
                if similarity is not None
                else ""
            )
            items.append(
                f"""      <article class="delta {sev_class(severity)}">
        <header><span class="clause">{html.escape(key)}</span>
          <span class="op">{OP_LABEL.get(op, op)}</span>{moved}{sim}</header>
        <div class="text">{body}</div>
      </article>"""
            )

        more = (
            f'<p class="muted more">{hidden} further changes in this revision are not '
            f"shown. Clausewatch displays changed clauses as excerpts only; read the "
            f'full instrument at <a href="{html.escape(source_url)}">MAS</a>.</p>'
            if hidden
            else ""
        )
        effective_note = (
            f" · effective {effective:%d %B %Y}" if isinstance(effective, date) else ""
        )
        comparisons.append(
            f"""  <section class="comparison">
    <h2>{to_date:%d %B %Y}</h2>
    <p class="meta">{len(rows)} clause{"s" if len(rows) != 1 else ""} changed since
      {from_date:%d %B %Y}{effective_note}</p>
{chr(10).join(items)}
{more}
  </section>"""
        )

    total = sum(len(r) for r in grouped.values())
    return f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(ref)} — clause-level changelog | Clausewatch</title>
<meta name="description" content="Every clause-level change to MAS {html.escape(ref)},
 reconstructed from the official published versions.">
<style>
:root {{
  --ink: #12161c; --muted: #5b6673; --line: #e3e7ec; --bg: #fbfcfd;
  --add: #10693a; --add-bg: #e6f4ec; --del: #96261f; --del-bg: #fbeceb;
  --high: #96261f; --med: #a86413; --low: #5b6673;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--bg); color: var(--ink);
  font: 17px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Georgia, serif;
  -webkit-font-smoothing: antialiased;
}}
.wrap {{ max-width: 46rem; margin: 0 auto; padding: 4rem 1.5rem 6rem; }}
h1 {{ font-size: 2rem; line-height: 1.2; margin: 0 0 .5rem; letter-spacing: -.02em; }}
h2 {{ font-size: 1.25rem; margin: 0 0 .25rem; letter-spacing: -.01em; }}
.lede {{ color: var(--muted); margin: 0 0 2.5rem; font-size: 1.05rem; }}
.brand {{ font-size: .8rem; letter-spacing: .12em; text-transform: uppercase;
  color: var(--muted); margin: 0 0 1.5rem; }}
.summary {{ border: 1px solid var(--line); background: #fff; border-radius: 6px;
  padding: 1.25rem 1.5rem; margin-bottom: 3rem; }}
.summary dl {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin: 0; }}
.summary dt {{ font-size: .78rem; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); }}
.summary dd {{ margin: .15rem 0 0; font-size: 1.5rem; font-variant-numeric: tabular-nums; }}
.comparison {{ margin-bottom: 3.5rem; }}
.meta {{ color: var(--muted); font-size: .92rem; margin: 0 0 1.25rem; }}
.delta {{ border-left: 3px solid var(--low); background: #fff;
  border-radius: 0 4px 4px 0; padding: .9rem 1.1rem; margin-bottom: .9rem;
  border-top: 1px solid var(--line); border-right: 1px solid var(--line);
  border-bottom: 1px solid var(--line); }}
.delta.high {{ border-left-color: var(--high); }}
.delta.med {{ border-left-color: var(--med); }}
.delta header {{ display: flex; gap: .6rem; align-items: baseline;
  flex-wrap: wrap; margin-bottom: .5rem; }}
.clause {{ font-weight: 700; font-variant-numeric: tabular-nums; }}
.op {{ font-size: .74rem; letter-spacing: .07em; text-transform: uppercase;
  color: var(--muted); border: 1px solid var(--line); border-radius: 3px;
  padding: .05rem .4rem; }}
.moved, .sim {{ font-size: .8rem; color: var(--muted); }}
.text {{ font-size: .95rem; }}
ins {{ background: var(--add-bg); color: var(--add); text-decoration: none;
  padding: .05em .12em; border-radius: 2px; }}
del {{ background: var(--del-bg); color: var(--del); padding: .05em .12em;
  border-radius: 2px; }}
.muted {{ color: var(--muted); }}
.more {{ font-size: .9rem; font-style: italic; }}
footer {{ border-top: 1px solid var(--line); margin-top: 4rem; padding-top: 1.5rem;
  color: var(--muted); font-size: .87rem; }}
a {{ color: inherit; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --ink: #e6e9ee; --muted: #9aa4b1; --line: #262c35; --bg: #0e1116;
    --add: #6fd39b; --add-bg: #12301f; --del: #f3968f; --del-bg: #331616; }}
  .summary, .delta {{ background: #141920; }}
}}
</style>
<div class="wrap">
<p class="brand">Clausewatch</p>
<h1>MAS {html.escape(ref)} — clause-level changelog</h1>
<p class="lede">{html.escape(title)}. Every clause-level change across the versions MAS
has published, reconstructed automatically from the official documents.</p>

<div class="summary">
  <dl>
    <dt>Versions compared</dt><dd>{len(grouped) + 1}</dd>
    <dt>Clause changes found</dt><dd>{total}</dd>
    <dt>Earliest version</dt><dd>2009</dd>
    <dt>Latest revision</dt><dd>2025</dd>
  </dl>
</div>

{chr(10).join(comparisons)}

<footer>
<p><strong>Source.</strong> Compiled from documents published by the Monetary Authority
of Singapore. Read the official instrument at
<a href="{html.escape(source_url)}">mas.gov.sg</a>. Where anything here differs from the
official publication, the official publication prevails.</p>
<p><strong>Not legal advice.</strong> Clausewatch reports what text changed. It does not
interpret legal effect, and it does not advise on obligations. Clausewatch is not
affiliated with or endorsed by the Monetary Authority of Singapore.</p>
<p><strong>Excerpts only.</strong> Only changed clauses are shown, as excerpts. This is
not a reproduction of the instrument.</p>
</footer>
</div>
"""


def main() -> int:
    with connection() as conn:
        instrument, deltas, counts = fetch(conn)
    grouped = group(deltas)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(instrument, grouped, counts), encoding="utf-8")
    total = sum(len(r) for r in grouped.values())
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
    print(f"{len(grouped)} comparisons, {total} deltas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
