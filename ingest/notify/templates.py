"""The two alert emails (T26).

The brief asks for two templates and is specific about why: a generic watchlist hit
tells a compliance officer that an instrument they follow moved, which is useful; a
mapped-control hit tells them that *their own* control AML-POL-4.2 is now out of date,
which is the thing they cannot get anywhere else and the reason a contract renews.

Three rules are enforced here rather than left to whoever edits the copy:

* **Descriptive only.** Legal Profession Act 1966 s.33. The same filter that guards the
  LLM output guards the rendered email, because a template is written once and read by
  a regulator later. `render_digest` raises rather than sending advice.
* **Never republish the corpus** (§4.3, §11). The email carries the summary, the clause
  number and a link to MAS. It does not carry clause text.
* **Escape everything.** Every string in here originates in a MAS PDF.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html import escape

from enrich.summarise import is_prescriptive

CONSOLE_URL = "https://jewlurk.github.io/clausewatch/app.html"

# Used when a change has no summary yet. Written as a sentence, because it stands
# where the summary would stand.
OP_WORDS = {
    "ADDED": "A new clause was added.",
    "REMOVED": "The clause was removed.",
    "MODIFIED": "The wording changed.",
    "RENUMBERED": "The clause number changed; the wording did not.",
}


class PrescriptiveEmail(RuntimeError):
    """The rendered email reads as advice. Refuse to send it."""


@dataclass(frozen=True)
class Alert:
    alert_id: int
    instrument_ref: str
    instrument_title: str
    source_url: str
    section_key: str
    op: str
    severity: int
    revision_date: date | None
    effective_date: date | None
    internal_ref: str | None
    ai_summary: str | None
    obligation_change: bool

    @property
    def mapped(self) -> bool:
        return bool(self.internal_ref)


@dataclass(frozen=True)
class Digest:
    recipient: str
    org_name: str
    alerts: tuple[Alert, ...]

    @property
    def mapped(self) -> tuple[Alert, ...]:
        return tuple(a for a in self.alerts if a.mapped)

    @property
    def watched(self) -> tuple[Alert, ...]:
        return tuple(a for a in self.alerts if not a.mapped)


def _when(alert: Alert) -> str:
    parts = []
    if alert.revision_date:
        parts.append(f"revised {alert.revision_date:%-d %B %Y}")
    if alert.effective_date and alert.effective_date != alert.revision_date:
        parts.append(f"effective {alert.effective_date:%-d %B %Y}")
    return ", ".join(parts)


def _line(alert: Alert) -> str:
    """One change, described. No interpretation, no recommendation."""
    what = alert.ai_summary or OP_WORDS.get(alert.op, "the clause changed")
    when = _when(alert)
    # Escaped before the em dash is joined in: escaping afterwards would turn the
    # entity into a literal "&mdash;" in the reader's inbox.
    head = escape(f"{alert.instrument_ref} {alert.section_key}")
    if alert.mapped:
        head = f"{escape(alert.internal_ref)} &mdash; {head}"
    tag = " (obligation changed)" if alert.obligation_change else ""
    return (
        f'<li style="margin:0 0 14px"><strong>{head}</strong>{tag}<br>'
        f'{escape(what)}<br>'
        f'<span style="color:#666;font-size:13px">{escape(when)} &middot; '
        f'<a href="{escape(alert.source_url)}" style="color:#b36800">official MAS page</a>'
        f"</span></li>"
    )


def _shell(title: str, intro: str, blocks: str) -> str:
    return f"""<!doctype html>
<html><body style="margin:0;background:#f6f6f4;font:15px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#1a1a1a">
<div style="max-width:600px;margin:0 auto;padding:28px 22px">
<p style="margin:0 0 4px;font:700 11px/1 ui-monospace,Menlo,monospace;letter-spacing:.22em;text-transform:uppercase;color:#b36800">Clausewatch</p>
<h1 style="margin:0 0 14px;font-size:20px;font-weight:650">{escape(title)}</h1>
<p style="margin:0 0 20px">{intro}</p>
{blocks}
<p style="margin:26px 0 0"><a href="{CONSOLE_URL}" style="color:#b36800">Open the console</a></p>
<hr style="border:0;border-top:1px solid #ddd;margin:26px 0 14px">
<p style="margin:0;color:#666;font-size:12px">
Clausewatch reports what text changed in a MAS instrument. It does not interpret legal
effect or advise on obligations, and it is not affiliated with the Monetary Authority of
Singapore. Where anything here differs from the official MAS publication, the official
publication prevails.</p>
<p style="margin:10px 0 0;color:#666;font-size:12px">
Free through 31 March 2027. From 1 April 2027, SGD 499/month per licensed entity
(SGD 1,200/month consultancy licence). Cancel anytime.</p>
</div></body></html>"""


def render_mapped(digest: Digest) -> tuple[str, str]:
    """The template that renews contracts: a change to a clause they mapped a control to."""
    mapped, watched = digest.mapped, digest.watched
    first = mapped[0]
    subject = (
        f"{first.internal_ref}: {first.instrument_ref} {first.section_key} changed"
        if len(mapped) == 1
        else f"{len(mapped)} of your controls reference clauses that changed"
    )
    intro = (
        f"{len(mapped)} clause{'s' if len(mapped) != 1 else ''} you have mapped a control "
        f"to changed in the latest MAS revision."
    )
    blocks = (
        '<p style="margin:0 0 8px;font:700 11px/1 ui-monospace,Menlo,monospace;'
        'letter-spacing:.16em;text-transform:uppercase;color:#b36800">Your controls</p>'
        f'<ul style="margin:0;padding-left:18px">{"".join(_line(a) for a in mapped)}</ul>'
    )
    if watched:
        blocks += (
            '<p style="margin:24px 0 8px;font:700 11px/1 ui-monospace,Menlo,monospace;'
            'letter-spacing:.16em;text-transform:uppercase;color:#b36800">'
            'Also on your watchlist</p>'
            f'<ul style="margin:0;padding-left:18px">{"".join(_line(a) for a in watched)}</ul>'
        )
    return subject, _shell("A clause one of your controls depends on changed", intro, blocks)


def render_watchlist(digest: Digest) -> tuple[str, str]:
    """The generic template: an instrument the org follows was revised."""
    alerts = digest.watched
    refs = sorted({a.instrument_ref for a in alerts})
    subject = (
        f"{refs[0]}: {len(alerts)} clause change{'s' if len(alerts) != 1 else ''}"
        if len(refs) == 1
        else f"{len(alerts)} clause changes across {len(refs)} instruments you follow"
    )
    intro = (
        f"{len(alerts)} clause{'s' if len(alerts) != 1 else ''} changed in "
        f"{', '.join(escape(r) for r in refs)}, which your organisation follows. "
        "None of these clauses has a control mapped to it yet."
    )
    blocks = f'<ul style="margin:0;padding-left:18px">{"".join(_line(a) for a in alerts)}</ul>'
    return subject, _shell("Instruments you follow were revised", intro, blocks)


def render_digest(digest: Digest) -> tuple[str, str]:
    """Pick the template and refuse anything that reads as advice."""
    if not digest.alerts:
        raise ValueError("nothing to send")
    subject, html = render_mapped(digest) if digest.mapped else render_watchlist(digest)
    for field_name, text in (("subject", subject), ("body", html)):
        if is_prescriptive(text):
            raise PrescriptiveEmail(
                f"{field_name} reads as advice, which s.33 does not allow us to give: {text[:160]}"
            )
    return subject, html
