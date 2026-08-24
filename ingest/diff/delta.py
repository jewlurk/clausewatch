"""compute_delta — the product. Brief §9.

Three passes:
  1. same clause number         — cheap, catches most real changes
  2. clause numbers that vanished — hunt the new version for the same text under a
     different number, so an inserted paragraph does not report N phantom changes
  3. genuinely new clauses

Pass 2 is the whole reason this is a product rather than a PDF diff.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .diff_html import diff_html
from .severity import score_severity
from .similarity import similarity

RENUMBER_THRESHOLD = 0.72  # tuned in T20; see docs/threshold-tuning.md
MODIFY_FLOOR = 0.35

ADDED, REMOVED, MODIFIED, RENUMBERED = "ADDED", "REMOVED", "MODIFIED", "RENUMBERED"


class SectionLike(Protocol):
    section_key: str
    body: str

    @property
    def body_sha256(self) -> str: ...


@dataclass
class Delta:
    op: str
    old_section_key: str | None
    new_section_key: str | None
    similarity: float | None
    severity: int
    diff_html: str | None = None
    obligation_change: bool = False
    meta: dict = field(default_factory=dict)


class Matcher(Protocol):
    """Finds the best-matching section in the target version.

    Production uses SQL over the pg_trgm GIN index (T16); tests and threshold tuning
    use the in-memory implementation below. Both must use the same similarity measure.
    """

    def best_match(
        self, body: str, candidates: dict[str, SectionLike]
    ) -> tuple[str, float] | None: ...


class InMemoryMatcher:
    """Reference matcher. O(n) per lookup — fine for tuning, not for production."""

    def best_match(
        self, body: str, candidates: dict[str, SectionLike]
    ) -> tuple[str, float] | None:
        best: tuple[str, float] | None = None
        for key, section in candidates.items():
            score = similarity(body, section.body)
            if best is None or score > best[1]:
                best = (key, score)
        return best


def _make_delta(
    op: str,
    old: SectionLike | None,
    new: SectionLike | None,
    sim: float | None,
) -> Delta:
    old_body = old.body if old else None
    new_body = new.body if new else None

    if op == REMOVED:
        severity = score_severity(old_body, old_body or "")
        severity = max(severity, 3)  # a deleted obligation is never cosmetic
        rendered = None
    elif op == ADDED:
        severity = score_severity(None, new_body or "")
        rendered = None
    elif op == RENUMBERED:
        severity = 2  # text identical, only the number moved
        rendered = None
    else:  # MODIFIED
        severity = score_severity(old_body, new_body or "")
        rendered = diff_html(old_body or "", new_body or "")

    return Delta(
        op=op,
        old_section_key=old.section_key if old else None,
        new_section_key=new.section_key if new else None,
        similarity=sim,
        severity=severity,
        diff_html=rendered,
    )


def compute_delta(
    old_sections: list[SectionLike],
    new_sections: list[SectionLike],
    matcher: Matcher | None = None,
    renumber_threshold: float = RENUMBER_THRESHOLD,
) -> list[Delta]:
    """Compare two parsed versions. Returns deltas with severity >= 2.

    Deterministic and idempotent: the same inputs always produce the same list, so
    re-running a crawl cannot create duplicate rows.
    """
    matcher = matcher or InMemoryMatcher()
    old = {s.section_key: s for s in old_sections}
    new = {s.section_key: s for s in new_sections}

    out: list[Delta] = []
    # Two sets, deliberately. Brief §9 uses one `matched_new` for both sides, but old
    # and new keys live in the same namespace: once new "6.3" is claimed by old "6.2",
    # a single set also marks old "6.3" as handled and silently drops it. Renumbering
    # a run of clauses is exactly when every key is claimed by its predecessor.
    matched_new: set[str] = set()
    handled_old: set[str] = set()

    # PASS 1 — same clause number.
    #
    # Deviation from brief §9, and it matters: the brief accepts every same-number pair
    # as MODIFIED. When a clause is inserted mid-document and everything below shifts
    # up one, each shifted number then holds unrelated text, and Pass 1 reports the
    # whole tail as MODIFIED — the exact phantom-change failure Pass 2 exists to
    # prevent, because Pass 2 never sees those clauses. So a same-number pair whose
    # bodies are unrelated (similarity < MODIFY_FLOOR) is deferred to Pass 2 instead.
    for key, old_section in old.items():
        new_section = new.get(key)
        if new_section is None:
            continue
        if old_section.body_sha256 == new_section.body_sha256:
            matched_new.add(key)
            handled_old.add(key)
            continue  # UNCHANGED: emit nothing, ever
        score = similarity(old_section.body, new_section.body)
        if score < MODIFY_FLOOR:
            continue  # unrelated text under a reused number — let Pass 2 hunt it
        matched_new.add(key)
        handled_old.add(key)
        out.append(_make_delta(MODIFIED, old_section, new_section, score))

    # PASS 2 — clause numbers that vanished. Before declaring REMOVED, hunt the new
    # version for the same text under a different number.
    for key, old_section in old.items():
        if key in handled_old:
            continue
        candidates = {k: v for k, v in new.items() if k not in matched_new}
        best = matcher.best_match(old_section.body, candidates) if candidates else None
        if best and best[1] >= renumber_threshold:
            cand_key, score = best
            cand = new[cand_key]
            matched_new.add(cand_key)
            op = RENUMBERED if cand.body_sha256 == old_section.body_sha256 else MODIFIED
            out.append(_make_delta(op, old_section, cand, score))
        else:
            out.append(_make_delta(REMOVED, old_section, None, None))

    # PASS 3 — genuinely new clauses.
    for key, new_section in new.items():
        if key not in matched_new:
            out.append(_make_delta(ADDED, None, new_section, None))

    out.sort(key=lambda d: (d.new_section_key or d.old_section_key or ""))
    return [d for d in out if d.severity >= 2]
