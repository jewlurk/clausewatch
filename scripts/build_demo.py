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
/* Terminal palette, but prose is set in a readable face. Monospace is right for
   clause numbers and diffs — identifiers you scan and compare character by character —
   and wrong for sentences you actually read. */
:root {
  --bg:#0a0a0b; --panel:#121214; --panel-2:#17171a; --line:#2a2a2f;
  --ink:#f2f2f3; --dim:#9a9aa2; --faint:#6d6d75;
  --amber:#ff9a2e; --amber-dim:#b36800; --amber-bg:#2e1c02;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, system-ui, sans-serif;
  --radius: 14px; --radius-sm: 7px;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.7 var(--sans); -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
.wrap { max-width: 68rem; margin: 0 auto; padding: 4.5rem 2.5rem 8rem; }
a { color: var(--amber); text-underline-offset: 2px; }

.brand { color: var(--amber); font-family: var(--mono); font-size: .74rem;
  letter-spacing: .24em; text-transform: uppercase; margin: 0 0 1rem; font-weight: 600; }
h1 { font-size: 2.4rem; font-weight: 680; letter-spacing: -.025em; line-height: 1.12;
  margin: 0 0 1rem; color: #fff; }
.lede { color: var(--dim); margin: 0 0 3rem; max-width: 42rem; font-size: 1.08rem;
  line-height: 1.7; }

/* Stat band — a single rounded panel of tiles. */
.summary { border: 1px solid var(--line); background: var(--panel);
  border-radius: var(--radius); margin-bottom: 3.5rem; overflow: hidden; }
.summary dl { display: grid; grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 0; margin: 0; }
.summary div { padding: 1.6rem 1.8rem; border-right: 1px solid var(--line); }
.summary div:last-child { border-right: 0; }
.summary dt { font-family: var(--mono); font-size: .68rem; letter-spacing: .16em;
  text-transform: uppercase; color: var(--dim); }
.summary dd { margin: .55rem 0 0; font-size: 2rem; color: var(--amber);
  font-variant-numeric: tabular-nums; font-weight: 650; letter-spacing: -.02em; }
.checked { margin: 0; padding: 1.05rem 1.8rem; border-top: 1px solid var(--line);
  font-size: .9rem; color: var(--dim); background: rgba(255,255,255,.015); }
.checked strong { color: var(--ink); }

.section { margin: 3.5rem 0 .5rem; font-family: var(--mono); font-size: .74rem;
  letter-spacing: .2em; text-transform: uppercase; color: var(--amber); font-weight: 700; }
.meta { color: var(--dim); font-size: .95rem; margin: 0 0 1.6rem; max-width: 42rem;
  line-height: 1.65; }

/* Instrument cards — separated, rounded, they lift on hover. */
.card { display: block; border: 1px solid var(--line); background: var(--panel);
  border-radius: var(--radius); padding: 1.35rem 1.6rem; margin-bottom: .7rem;
  text-decoration: none; color: inherit;
  transition: border-color .15s ease, background .15s ease, transform .15s ease; }
.card:hover { background: var(--panel-2); border-color: #454550; transform: translateY(-1px); }
.card h2 { margin: 0 0 .3rem; font-size: 1.1rem; color: var(--amber); font-weight: 650; }
.card .meta { margin: 0; font-size: .9rem; }
.tag { display: inline-block; font-family: var(--mono); font-size: .64rem;
  letter-spacing: .12em; text-transform: uppercase; color: var(--dim);
  border: 1px solid var(--line); border-radius: 999px; padding: .18rem .55rem;
  margin-right: .35rem; line-height: 1; }

.comparison { margin-bottom: 4rem; }
h2 { font-size: 1.25rem; margin: 0 0 .3rem; color: #fff; font-weight: 650;
  letter-spacing: -.01em; }

/* One change. The summary is the content; the wording is evidence you open. */
.delta { border: 1px solid var(--line); border-left: 3px solid var(--line);
  background: var(--panel); border-radius: var(--radius); padding: 1.35rem 1.6rem;
  margin-bottom: .7rem; transition: border-color .15s ease; }
.delta:hover { border-color: #3a3a42; }
.delta.high { border-left-color: var(--amber); }
.delta.med { border-left-color: var(--amber-dim); }
.delta header { display: flex; gap: .6rem; align-items: center; flex-wrap: wrap;
  margin-bottom: .7rem; }
.clause { font-family: var(--mono); font-weight: 700; color: var(--amber);
  font-size: .98rem; }
.op { font-family: var(--mono); font-size: .64rem; letter-spacing: .12em;
  text-transform: uppercase; color: var(--dim); border: 1px solid var(--line);
  border-radius: 999px; padding: .18rem .55rem; line-height: 1; }
.ob { font-family: var(--mono); font-size: .64rem; letter-spacing: .12em;
  text-transform: uppercase; color: #1a1000; background: var(--amber);
  border-radius: 999px; padding: .2rem .55rem; font-weight: 700; line-height: 1; }
.moved, .sim { font-size: .85rem; color: var(--dim); font-family: var(--mono); }
.sum { margin: 0 0 .6rem; color: var(--ink); font-size: 1.04rem; line-height: 1.65;
  max-width: 60rem; }
.nosum { margin: 0 0 .6rem; color: var(--dim); font-size: .96rem; font-style: italic; }

details { margin-top: .6rem; }
summary { cursor: pointer; font-family: var(--mono); font-size: .7rem;
  letter-spacing: .12em; text-transform: uppercase; color: var(--dim);
  list-style: none; padding: .25rem 0; transition: color .12s ease; }
summary::-webkit-details-marker { display: none; }
summary:hover { color: var(--amber); }
summary::before { content: "▸ "; }
details[open] summary::before { content: "▾ "; }
.text { font-family: var(--mono); font-size: .85rem; line-height: 1.75;
  color: var(--dim); margin-top: .7rem; padding: 1.1rem 1.25rem; background: #060607;
  border: 1px solid var(--line); border-radius: var(--radius-sm); overflow-x: auto; }
ins { background: var(--amber-bg); color: var(--amber); text-decoration: none;
  border-radius: 3px; padding: 0 .1em; }
del { background: transparent; color: #6e6e6e; text-decoration: line-through; }
.muted, .gap { color: var(--faint); }
.more { font-size: .92rem; color: var(--dim); margin: 1.1rem 0 0; }
.back { display: inline-block; margin-bottom: 1.8rem; font-size: .9rem;
  color: var(--dim); text-decoration: none; font-family: var(--mono); }
.back:hover { color: var(--amber); }

footer { border-top: 1px solid var(--line); margin-top: 5rem; padding-top: 1.8rem;
  color: var(--dim); font-size: .9rem; max-width: 50rem; line-height: 1.7; }
footer p { margin: 0 0 .8rem; }
footer strong { color: var(--ink); }
@media (max-width: 700px) {
  .wrap { padding: 2.75rem 1.25rem 5rem; }
  h1 { font-size: 1.95rem; }
  .summary div { padding: 1.2rem 1.4rem; }
  .card, .delta { padding: 1.1rem 1.25rem; }
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


def summary_block(ai_summary: str | None, op: str) -> str:
    """What the change means, in a sentence.

    When no summary exists the absence is stated rather than papered over — a reader
    should never wonder whether a blank line means "nothing happened".
    """
    if ai_summary:
        return f'    <p class="sum">{html.escape(ai_summary)}</p>'
    fallback = {
        "RENUMBERED": "Clause number changed; wording unchanged.",
        "REMOVED": "Clause removed from the instrument.",
    }.get(op, "No summary generated for this change — see the wording below.")
    return f'    <p class="nosum">{fallback}</p>'


def revision_headline(rows) -> str:
    """One line describing a revision as a whole, before the clause-by-clause detail.

    The obligation count used to read the wrong column and so counted every clause
    with a body, which is almost all of them. Same off-by-one as the summary line.
    """
    obligations = sum(1 for r in rows if col(r, "obligation_change"))
    added = sum(1 for r in rows if col(r, "op") == "ADDED")
    modified = sum(1 for r in rows if col(r, "op") == "MODIFIED")
    removed = sum(1 for r in rows if col(r, "op") == "REMOVED")
    parts = []
    if added:
        parts.append(f"{added} new clause{'s' if added != 1 else ''}")
    if modified:
        parts.append(f"{modified} amended")
    if removed:
        parts.append(f"{removed} removed")
    line = ", ".join(parts) or f"{len(rows)} changes"
    if obligations:
        line += (
            f" · {obligations} change{'s' if obligations != 1 else ''} affecting an obligation"
        )
    return line


def sev_class(severity: int) -> str:
    return "high" if severity >= 4 else "med" if severity == 3 else "low"


# What makes a change worth a compliance officer's attention, in order of weight.
# A renumbering is real but carries no new obligation, so it must never outrank a
# threshold change. Severity already encodes added modals, changed numbers and dates
# (see diff/severity.py); this adds the operation and recency dimensions.
OP_WEIGHT = {"ADDED": 3, "MODIFIED": 3, "REMOVED": 2, "RENUMBERED": 0}

# Slots any single instrument may take in the front-page feed.
PER_INSTRUMENT_CAP = 3
EXCERPT_WORDS = 45


def excerpt(text: str, words: int = EXCERPT_WORDS) -> str:
    parts = text.split()
    return " ".join(parts[:words]) + ("\u2026" if len(parts) > words else "")


def importance(op: str, severity: int, revision: date | None, newest: date | None,
               obligation_change: bool = False) -> float:
    """Rank a change for the front page. Higher is more worth reading.

    Severity is a deterministic heuristic — it cannot tell a substantive reword from a
    trivial one, so two MODIFIED clauses that both changed a word but neither a number
    nor a modal land on the same default of 3. `obligation_change` is the signal that
    separates them: the summariser sets it when the change alters what a firm must do,
    which is exactly the change a compliance officer reads first. It is worth about one
    severity point, enough to lift a real obligation change above an incidental reword
    of the same nominal severity without letting it leap a genuinely heavier change.
    """
    score = severity * 2 + OP_WEIGHT.get(op, 1)
    if obligation_change:
        score += 2
    if revision and newest:
        # Decay by revision age so the current amendment leads, without burying an
        # older high-severity change entirely.
        years = max(0.0, (newest - revision).days / 365.0)
        score -= min(years * 1.2, 6.0)
    return score


def render_recent(rows, limit: int = 12) -> str:
    """The front-page feed: the changes that actually matter, newest and heaviest first."""
    newest = max((col(r, "to_date") for r in rows if col(r, "to_date")), default=None)
    ranked = sorted(
        rows,
        key=lambda r: importance(col(r, "op"), col(r, "severity"),
                                 col(r, "to_date"), newest,
                                 col(r, "obligation_change")),
        reverse=True,
    )
    # Cap per instrument. Ranking alone let SFA04-N02's 2025 restatement fill every
    # slot, which reads as one event rather than as coverage.
    per_instrument: dict[int, int] = {}
    selected = []
    for row in ranked:
        count = per_instrument.get(col(row, "instrument_id"), 0)
        if count >= PER_INSTRUMENT_CAP:
            continue
        per_instrument[col(row, "instrument_id")] = count + 1
        selected.append(row)
        if len(selected) >= limit:
            break

    entries = []
    for row in selected:
        op, ref, url = col(row, "op"), col(row, "external_ref"), col(row, "source_url")
        new_key, old_key = col(row, "new_key"), col(row, "old_key")
        severity, to_date = col(row, "severity"), col(row, "to_date")
        diff_text, new_body = col(row, "diff_html"), col(row, "new_body")
        ai_summary, obligation = col(row, "ai_summary"), col(row, "obligation_change")
        key = new_key or old_key or "\u2014"
        if diff_text:
            body = window(diff_text)
        elif op == "ADDED" and new_body:
            body = f"<ins>{html.escape(excerpt(new_body))}</ins>"
        else:
            body = (
                '<span class="muted">New clause \u2014 read it at MAS.</span>'
                if op == "ADDED"
                else '<span class="muted">Clause removed.</span>'
            )
        when = f"{to_date:%b %Y}" if to_date else ""
        flag = '<span class="ob">obligation</span>' if obligation else ""
        entries.append(
            f"""  <article class="delta {sev_class(severity)}">
    <header><a class="src" href="{html.escape(url)}">{html.escape(ref)}</a>
      <span class="clause">{html.escape(key)}</span>
      <span class="op">{OP_LABEL.get(op, op)}</span>{flag}
      <span class="sim">{when}</span></header>
{summary_block(ai_summary, op)}
    <details><summary>Exact wording</summary>
      <div class="text">{body}</div></details>
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


# The delta query's columns, named. They used to be positional, and
# render_instrument sliced the wrong ones: `ns.body` landed in the slot
# render code read as `ai_summary`, so every clause without a real summary was
# published with its full text in the summary line — up to 1,764 words of MAS's
# own wording on a public page, which §11 forbids outright. Indexing by name is
# what stops that recurring.
DELTA_COLUMNS = {
    "instrument_id": "d.instrument_id",
    "from_version_id": "d.from_version_id",
    "to_version_id": "d.to_version_id",
    "from_date": "fv.issue_date",
    "to_date": "tv.issue_date",
    "effective_date": "tv.effective_date",
    "op": "d.op",
    "new_key": "d.new_section_key",
    "old_key": "d.old_section_key",
    "severity": "d.severity",
    "diff_html": "d.diff_html",
    "similarity": "d.similarity",
    "external_ref": "i.external_ref",
    "source_url": "i.source_url",
    "new_body": "ns.body",
    "ai_summary": "d.ai_summary",
    "obligation_change": "d.obligation_change",
}
COL = {name: index for index, name in enumerate(DELTA_COLUMNS)}


def col(row, name):
    return row[COL[name]]


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
            f"""
            select {", ".join(DELTA_COLUMNS.values())}
            from deltas d
            join instruments i on i.id = d.instrument_id
            left join sections ns on ns.id = d.new_section_id
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
        revision = tuple(col(row, name) for name in
                         ("from_version_id", "to_version_id", "from_date",
                          "to_date", "effective_date"))
        grouped.setdefault(revision, []).append(row)

    sections_html = []
    for (_fid, to_id, from_date, to_date, effective), items in grouped.items():
        clause_total = counts.get(to_id, 0) or 1
        cap = max(1, int(clause_total * EXCERPT_CAP))
        shown, hidden = items[:cap], max(0, len(items) - cap)

        entries = []
        for row in shown:
            op, severity = col(row, "op"), col(row, "severity")
            new_key, old_key = col(row, "new_key"), col(row, "old_key")
            diff_text, similarity = col(row, "diff_html"), col(row, "similarity")
            ai_summary = col(row, "ai_summary")
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
{summary_block(ai_summary, op)}
      <details><summary>Exact wording</summary>
        <div class="text">{body}</div></details>
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
        to_label = f"{to_date:%d %B %Y}" if isinstance(to_date, date) else "Undated revision"
        from_label = f"{from_date:%d %B %Y}" if isinstance(from_date, date) else "an earlier version"
        sections_html.append(
            f"""  <section class="comparison">
    <h2>{to_label}</h2>
    <p class="meta">{revision_headline(items)} · since {from_label}{eff}</p>
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
  <div><dt>Versions</dt><dd>{len(grouped) + 1 if grouped else 0}</dd></div>
  <div><dt>Clause changes</dt><dd>{total}</dd></div>
  <div><dt>Latest revision</dt><dd>{latest_text}</dd></div>
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
  <div><dt>Instruments</dt><dd>{tracked}</dd></div>
  <div><dt>Clause changes</dt><dd>{changes}</dd></div>
  <div><dt>Latest change</dt><dd>{latest_text}</dd></div>
</dl>
<p class="checked">{checked} Checked daily.</p></div>

<h2 class="section">What changed recently</h2>
<p class="meta">The changes most likely to need action, ranked by how much they alter an
obligation and how recent they are. Renumbering and formatting rank below substance.</p>
{recent_html}

<h2 class="section">Console</h2>
<p class="meta">Map your internal controls to clauses and get told when they change.
Free through 31 March 2027.
<a href="app.html">Open the console &rarr;</a> &nbsp;·&nbsp;
<a href="guide.html">How it works &rarr;</a></p>

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
        by_instrument.setdefault(col(row, "instrument_id"), []).append(row)

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
