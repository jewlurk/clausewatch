"""Generate the public changelog site (T21 / gate G2).

An index plus one page per instrument, all static. No framework, no CSS library, one
stylesheet shared by both templates — brief §4.2. Credibility comes from typography
and from the data being right, not from dependencies.

§11 guard, enforced here rather than trusted: a comparison may display at most
EXCERPT_CAP of an instrument's clauses. A full restatement changes more clauses than
the document contains, so rendering every delta would effectively republish the
instrument, which §4.3 forbids. Anything above the cap is summarised and deep-linked
to MAS.
"""
from __future__ import annotations

import html
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ingest"))

from db import connection

OUT_DIR = Path(__file__).resolve().parent.parent / "web"
EXCERPT_CAP = 0.40
CONTEXT_WORDS = 22

_SEGMENT_RE = re.compile(r"(<(?:ins|del)>.*?</(?:ins|del)>)", re.DOTALL)

OP_LABEL = {
    "ADDED": "Added",
    "REMOVED": "Removed",
    "MODIFIED": "Modified",
    "RENUMBERED": "Renumbered",
}

STYLE = """
:root {
  --ink: #12161c; --muted: #5b6673; --line: #e3e7ec; --bg: #fbfcfd;
  --add: #10693a; --add-bg: #e6f4ec; --del: #96261f; --del-bg: #fbeceb;
  --high: #96261f; --med: #a86413; --low: #96a1ae; --accent: #1d4ed8;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 17px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Georgia, serif;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 46rem; margin: 0 auto; padding: 3.5rem 1.5rem 6rem; }
h1 { font-size: 2.05rem; line-height: 1.18; margin: 0 0 .6rem; letter-spacing: -.022em; }
h2 { font-size: 1.22rem; margin: 0 0 .2rem; letter-spacing: -.01em; }
.lede { color: var(--muted); margin: 0 0 2.5rem; font-size: 1.05rem; }
.brand { font-size: .78rem; letter-spacing: .14em; text-transform: uppercase;
  color: var(--muted); margin: 0 0 1.4rem; }
.brand a { text-decoration: none; }
.summary { border: 1px solid var(--line); background: #fff; border-radius: 6px;
  padding: 1.2rem 1.4rem; margin-bottom: 2.75rem; }
.summary dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(9rem, 1fr));
  gap: 1rem; margin: 0; }
.summary dt { font-size: .74rem; letter-spacing: .09em; text-transform: uppercase;
  color: var(--muted); }
.summary dd { margin: .15rem 0 0; font-size: 1.5rem; font-variant-numeric: tabular-nums; }
.card { display: block; border: 1px solid var(--line); background: #fff;
  border-radius: 6px; padding: 1.1rem 1.3rem; margin-bottom: .85rem;
  text-decoration: none; color: inherit; }
.card:hover { border-color: var(--accent); }
.card h2 { margin-bottom: .15rem; }
.card .meta { margin: 0; }
.tag { display: inline-block; font-size: .72rem; letter-spacing: .06em;
  text-transform: uppercase; color: var(--muted); border: 1px solid var(--line);
  border-radius: 3px; padding: .05rem .4rem; margin-right: .3rem; }
.comparison { margin-bottom: 3.25rem; }
.meta { color: var(--muted); font-size: .92rem; margin: 0 0 1.15rem; }
.delta { border-left: 3px solid var(--low); background: #fff;
  border-radius: 0 4px 4px 0; padding: .85rem 1.05rem; margin-bottom: .85rem;
  border-top: 1px solid var(--line); border-right: 1px solid var(--line);
  border-bottom: 1px solid var(--line); }
.delta.high { border-left-color: var(--high); }
.delta.med { border-left-color: var(--med); }
.delta header { display: flex; gap: .55rem; align-items: baseline;
  flex-wrap: wrap; margin-bottom: .45rem; }
.clause { font-weight: 700; font-variant-numeric: tabular-nums; }
.op { font-size: .72rem; letter-spacing: .07em; text-transform: uppercase;
  color: var(--muted); border: 1px solid var(--line); border-radius: 3px;
  padding: .05rem .4rem; }
.moved, .sim { font-size: .8rem; color: var(--muted); }
.text { font-size: .95rem; }
ins { background: var(--add-bg); color: var(--add); text-decoration: none;
  padding: .05em .12em; border-radius: 2px; }
del { background: var(--del-bg); color: var(--del); padding: .05em .12em;
  border-radius: 2px; }
.muted { color: var(--muted); }
.gap { color: var(--muted); font-size: .85em; }
.more { font-size: .9rem; font-style: italic; }
.checked { margin: 1rem 0 0; padding-top: .9rem; border-top: 1px solid var(--line);
  font-size: .88rem; color: var(--muted); }
.section { margin: 2.75rem 0 .3rem; font-size: 1.05rem; letter-spacing: .01em; }
.src { font-weight: 700; text-decoration: none; border-bottom: 1px solid var(--line); }
.back { display: inline-block; margin-bottom: 1.4rem; font-size: .9rem;
  color: var(--muted); }
footer { border-top: 1px solid var(--line); margin-top: 4rem; padding-top: 1.4rem;
  color: var(--muted); font-size: .86rem; }
a { color: inherit; }
@media (prefers-color-scheme: dark) {
  :root { --ink: #e6e9ee; --muted: #9aa4b1; --line: #262c35; --bg: #0e1116;
    --add: #6fd39b; --add-bg: #12301f; --del: #f3968f; --del-bg: #331616;
    --accent: #7ba3ff; }
  .summary, .delta, .card { background: #141920; }
}
"""

FOOTER = """<footer>
<p><strong>Source.</strong> Compiled from documents published by the Monetary Authority
of Singapore. Where anything here differs from the official publication, the official
publication prevails.</p>
<p><strong>Not legal advice.</strong> Clausewatch reports what text changed. It does not
interpret legal effect and does not advise on obligations. Clausewatch is not affiliated
with or endorsed by the Monetary Authority of Singapore.</p>
<p><strong>Excerpts only.</strong> Only changed clauses are shown, as excerpts. This is
not a reproduction of any instrument.</p>
</footer>"""


def window(diff_html_text: str) -> str:
    """Keep changed spans plus context; elide long unchanged stretches.

    Splits on whole <ins>/<del> segments so a tag can never be broken. The input is
    already escaped and must stay well-formed.
    """
    parts = _SEGMENT_RE.split(diff_html_text)
    out: list[str] = []
    for index, part in enumerate(parts):
        if index % 2:
            out.append(part)
            continue
        words = part.split()
        if len(words) <= CONTEXT_WORDS * 2:
            out.append(part)
            continue
        ellipsis = ' <span class="gap">[…]</span> '
        head = " ".join(words[:CONTEXT_WORDS])
        tail = " ".join(words[-CONTEXT_WORDS:])
        if index == 0:
            out.append(ellipsis + tail)
        elif index == len(parts) - 1:
            out.append(head + ellipsis)
        else:
            out.append(head + ellipsis + tail)
    return "".join(out)


def sev_class(severity: int) -> str:
    return "high" if severity >= 4 else "med" if severity == 3 else "low"


# What makes a change worth a compliance officer's attention, in order of weight.
# A renumbering is real but carries no new obligation, so it must never outrank a
# threshold change. Severity already encodes added modals, changed numbers and dates
# (see diff/severity.py); this adds the operation and recency dimensions.
OP_WEIGHT = {"ADDED": 3, "MODIFIED": 3, "REMOVED": 2, "RENUMBERED": 0}


def importance(op: str, severity: int, revision: date | None, newest: date | None) -> float:
    """Rank a change for the front page. Higher is more worth reading."""
    score = severity * 2 + OP_WEIGHT.get(op, 1)
    if revision and newest:
        # Decay by revision age so the current amendment leads, without burying an
        # older high-severity change entirely.
        years = max(0.0, (newest - revision).days / 365.0)
        score -= min(years * 1.2, 6.0)
    return score


def render_recent(rows, limit: int = 12) -> str:
    """The front-page feed: the changes that actually matter, newest and heaviest first."""
    newest = max((r[4] for r in rows if r[4]), default=None)
    ranked = sorted(
        rows,
        key=lambda r: importance(r[6], r[9], r[4], newest),
        reverse=True,
    )
    entries = []
    for row in ranked[:limit]:
        _iid, _fid, _tid, _fd, to_date, _eff, op, new_key, old_key, severity, diff_text, _sim = row
        ref, url = row[12], row[13]
        key = new_key or old_key or "\u2014"
        body = (window(diff_text) if diff_text else None) or (
            '<span class="muted">New clause \u2014 read it at MAS.</span>'
            if op == "ADDED"
            else '<span class="muted">Clause removed.</span>'
        )
        when = f"{to_date:%b %Y}" if to_date else ""
        entries.append(
            f"""  <article class="delta {sev_class(severity)}">
    <header><a class="src" href="{html.escape(url)}">{html.escape(ref)}</a>
      <span class="clause">{html.escape(key)}</span>
      <span class="op">{OP_LABEL.get(op, op)}</span>
      <span class="sim">{when}</span></header>
    <div class="text">{body}</div>
  </article>"""
        )
    return chr(10).join(entries)


def slug(ref: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", ref.lower()).strip("-") + ".html"


def page(title: str, description: str, body: str) -> str:
    return f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(description)}">
<style>{STYLE}</style>
<div class="wrap">
{body}
{FOOTER}
</div>
"""


def fetch(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            select i.id, i.external_ref, i.title, i.source_url, i.applies_to
            from instruments i join regulators r on r.id = i.regulator_id
            where r.code = 'MAS' order by i.external_ref
            """
        )
        instruments = cur.fetchall()

        cur.execute(
            """
            select d.instrument_id, d.from_version_id, d.to_version_id,
                   fv.issue_date, tv.issue_date, tv.effective_date,
                   d.op, d.new_section_key, d.old_section_key,
                   d.severity, d.diff_html, d.similarity,
                   i.external_ref, i.source_url
            from deltas d
            join instruments i on i.id = d.instrument_id
            join instrument_versions fv on fv.id = d.from_version_id
            join instrument_versions tv on tv.id = d.to_version_id
            order by tv.issue_date desc, d.severity desc, d.new_section_key
            """
        )
        deltas = cur.fetchall()

        cur.execute("select version_id, count(*) from sections group by version_id")
        counts = dict(cur.fetchall())

        cur.execute(
            "select instrument_id, count(*) from instrument_versions group by instrument_id"
        )
        version_counts = dict(cur.fetchall())

        cur.execute(
            "select finished_at from crawl_runs where status = 'ok' "
            "and finished_at is not null order by finished_at desc limit 1"
        )
        row = cur.fetchone()
        last_checked = row[0] if row else None
    return instruments, deltas, counts, version_counts, last_checked


def render_instrument(instrument, rows, counts):
    _, ref, title, source_url, _ = instrument

    grouped: dict[tuple, list] = {}
    for row in rows:
        grouped.setdefault((row[1], row[2], row[3], row[4], row[5]), []).append(row[6:])

    sections_html = []
    for (_fid, to_id, from_date, to_date, effective), items in grouped.items():
        clause_total = counts.get(to_id, 0) or 1
        cap = max(1, int(clause_total * EXCERPT_CAP))
        shown, hidden = items[:cap], max(0, len(items) - cap)

        entries = []
        for op, new_key, old_key, severity, diff_text, similarity in shown:
            key = new_key or old_key or "—"
            moved = (
                f'<span class="moved">was {html.escape(old_key)}</span>'
                if op == "RENUMBERED" and old_key and old_key != new_key
                else ""
            )
            body = (window(diff_text) if diff_text else None) or (
                '<span class="muted">Clause added — read it at MAS.</span>'
                if op == "ADDED"
                else '<span class="muted">Clause removed.</span>'
                if op == "REMOVED"
                else '<span class="muted">Number changed; text unchanged.</span>'
            )
            sim = (
                f'<span class="sim">{similarity:.0%} similar</span>'
                if similarity is not None
                else ""
            )
            entries.append(
                f"""    <article class="delta {sev_class(severity)}">
      <header><span class="clause">{html.escape(key)}</span>
        <span class="op">{OP_LABEL.get(op, op)}</span>{moved}{sim}</header>
      <div class="text">{body}</div>
    </article>"""
            )

        more = (
            f'<p class="muted more">{hidden} further changes in this revision are not '
            f"shown — read the full instrument at "
            f'<a href="{html.escape(source_url)}">MAS</a>.</p>'
            if hidden
            else ""
        )
        eff = f" · effective {effective:%d %B %Y}" if isinstance(effective, date) else ""
        sections_html.append(
            f"""  <section class="comparison">
    <h2>{to_date:%d %B %Y}</h2>
    <p class="meta">{len(items)} clause{"s" if len(items) != 1 else ""} changed since
      {from_date:%d %B %Y}{eff}</p>
{chr(10).join(entries)}
{more}
  </section>"""
        )

    total = sum(len(v) for v in grouped.values())
    latest = max((k[3] for k in grouped), default=None)
    latest_text = f"{latest:%b %Y}" if latest else "—"
    body = f"""<p class="brand"><a href="index.html">Clausewatch</a></p>
<a class="back" href="index.html">← All instruments</a>
<h1>MAS {html.escape(ref)}</h1>
<p class="lede">{html.escape(title)}. Every clause-level change across the versions MAS
has published, reconstructed automatically from the official documents.
<a href="{html.escape(source_url)}">Official page at MAS →</a></p>

<div class="summary"><dl>
  <dt>Versions compared</dt><dd>{len(grouped) + 1 if grouped else 0}</dd>
  <dt>Clause changes</dt><dd>{total}</dd>
  <dt>Latest revision</dt><dd>{latest_text}</dd>
</dl></div>

{chr(10).join(sections_html)}"""
    return (
        page(
            f"MAS {ref} — clause-level changelog | Clausewatch",
            f"Every clause-level change to MAS {ref}, from the official versions.",
            body,
        ),
        total,
        latest,
    )


def render_index(cards, tracked, changes, latest, recent_html, last_checked) -> str:
    latest_text = f"{latest:%b %Y}" if latest else "—"
    # The reassurance line. In a month where nothing changed this is the whole value on
    # display: it separates "nothing happened" from "nobody looked".
    checked = (
        f"Corpus last checked against MAS on <strong>{last_checked:%d %B %Y}</strong>."
        if last_checked
        else "Corpus rebuilt from the official MAS documents."
    )
    body = f"""<p class="brand">Clausewatch</p>
<h1>Singapore AML/CFT — clause-level changelogs</h1>
<p class="lede">MAS republishes an entire PDF when it amends a notice; it does not
publish redlines. These changelogs reconstruct every clause-level change automatically
from the official documents, so you can see exactly what moved and when.</p>

<div class="summary"><dl>
  <dt>Instruments tracked</dt><dd>{tracked}</dd>
  <dt>Clause changes found</dt><dd>{changes}</dd>
  <dt>Most recent change</dt><dd>{latest_text}</dd>
</dl>
<p class="checked">{checked} Checked daily.</p></div>

<h2 class="section">What changed recently</h2>
<p class="meta">The changes most likely to need action, ranked by how much they alter an
obligation and how recent they are. Renumbering and formatting rank below substance.</p>
{recent_html}

<h2 class="section">All instruments</h2>
{chr(10).join(cards)}"""
    return page(
        "Singapore AML/CFT clause-level changelogs | Clausewatch",
        "Clause-level changelogs for MAS AML/CFT notices — banks, payment services, "
        "digital payment tokens, and capital markets intermediaries.",
        body,
    )


def main() -> int:
    with connection() as conn:
        instruments, deltas, counts, version_counts, last_checked = fetch(conn)

    by_instrument: dict[int, list] = {}
    for row in deltas:
        by_instrument.setdefault(row[0], []).append(row)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cards: list[str] = []
    grand_total = 0
    latest_overall = None
    tracked = 0

    for inst in instruments:
        iid, ref, _title, _url, applies = inst
        rows = by_instrument.get(iid, [])
        if not rows:
            print(f"  {ref}: no deltas — skipped")
            continue
        markup, total, latest = render_instrument(inst, rows, counts)
        (OUT_DIR / slug(ref)).write_text(markup, encoding="utf-8")
        grand_total += total
        tracked += 1
        if latest and (latest_overall is None or latest > latest_overall):
            latest_overall = latest

        tags = "".join(
            f'<span class="tag">{html.escape(a.replace("_", " "))}</span>'
            for a in (applies or [])
        )
        latest_text = f"{latest:%b %Y}" if latest else "—"
        cards.append(
            f"""<a class="card" href="{slug(ref)}">
  <h2>MAS {html.escape(ref)}</h2>
  <p class="meta">{tags} {total} clause changes ·
    {version_counts.get(iid, 0)} documents · latest {latest_text}</p>
</a>"""
        )
        print(f"  {ref}: {total} deltas -> {slug(ref)}")

    (OUT_DIR / "index.html").write_text(
        render_index(
            cards, tracked, grand_total, latest_overall,
            render_recent(deltas), last_checked,
        ),
        encoding="utf-8",
    )
    print(f"\n{tracked} instruments, {grand_total} deltas -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
