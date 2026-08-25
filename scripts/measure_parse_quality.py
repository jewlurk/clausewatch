"""Measure differ accuracy on every instrument MAS published a tracked copy for.

The 0%-false-positive figure in docs/threshold-tuning.md was measured on Notice 626
alone. This runs the same measurement across the corpus, so the accuracy claim covers
what we actually ship rather than one document.

Method, unchanged from measure_g1.py: MAS's own tracked-changes PDF is the ground
truth. A clause carrying coloured characters is a clause MAS marked as amended. We
diff the two clean consolidated versions either side of that revision and compare.

Note on which round is measured. STATE.md assumed other instruments had tracked copies
from the 30 June 2025 round; checked against the live landing pages on 26 August 2026,
they do not — 626 is the only 2025 tracked copy. The other ten have tracked copies from
the June 2021 round, so that is the round measured for them. It is the same test on a
different pair of versions.

Downloads are cached under --cache so a re-run costs MAS nothing. Rate limited at the
crawler's own 2s floor.

    .venv/bin/python scripts/measure_parse_quality.py
    .venv/bin/python scripts/measure_parse_quality.py --only "Notice 314" --verbose
"""
from __future__ import annotations

import argparse
import itertools
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ingest"))
sys.path.insert(0, str(ROOT / "scripts"))

# Same threshold the pipeline uses to tell a consolidated notice from a two-page
# amendment notice. Imported rather than restated so the two cannot drift.
from corpus import CONSOLIDATED_MIN_SECTIONS, TRACKED_MARKERS
from crawler.http import PoliteClient
from crawler.mas import MasAdapter
from diff.delta import compute_delta
from instruments import MAS_INSTRUMENTS
from mas_tracked_oracle import changed_clauses
from parse.dates import version_date
from parse.sections import extract_pdf_text, parse_pdf, parse_sections

GATE = 0.05


def slug(url: str) -> str:
    return url.rsplit("/", 1)[-1]


class Doc:
    def __init__(self, path: Path, label: str, url: str) -> None:
        self.path, self.label, self.url = path, label, url
        self.text = extract_pdf_text(path)
        self.sections = parse_sections(self.text)
        head = self.text[:4000].lower()
        self.tracked = any(m in head for m in TRACKED_MARKERS)
        self.consolidated = len(self.sections) >= CONSOLIDATED_MIN_SECTIONS
        self.date = version_date(self.text)

    def __repr__(self) -> str:
        kind = "tracked" if self.tracked else ("consolidated" if self.consolidated else "other")
        return f"<{self.date} {kind} {len(self.sections):>3} sections {slug(self.url)}>"


def fetch_all(client: PoliteClient, spec, cache: Path, verbose: bool) -> list[Doc]:
    page = client.fetch(spec.landing_url)
    refs = MasAdapter().discover(page.content.decode("utf-8", "replace"), spec.external_ref)
    docs = []
    for ref in refs:
        path = cache / f"{spec.external_ref.replace(' ', '_')}__{slug(ref.url)}"
        if not path.exists():
            try:
                path.write_bytes(client.fetch(ref.url).content)
            except Exception as exc:  # noqa: BLE001 — a dead link must not stop the run
                print(f"    skip {slug(ref.url)}: {exc}")
                continue
        try:
            docs.append(Doc(path, ref.label, ref.url))
        except Exception as exc:  # noqa: BLE001 — an unparseable PDF is data, not a crash
            print(f"    unparseable {slug(ref.url)}: {exc}")
    if verbose:
        for d in sorted(docs, key=lambda d: (d.date is None, d.date)):
            print("   ", d)
    return docs


def label_year(label: str) -> int | None:
    """The publication year MAS puts in the link text, e.g. 'Notice 314 (Amendment) 2021'.

    Preferred over the date parsed out of the PDF body for tracked copies specifically:
    a tracked copy repeats the previous revision's "last revised on" line in black, so
    Notice 314's June 2021 markup parses out as 30 November 2015.
    """
    years = re.findall(r"\b(19|20)\d{2}\b", label)
    if not years:
        return None
    return int(re.findall(r"\b((?:19|20)\d{2})\b", label)[-1])


def _squash(text: str) -> str:
    return " ".join(text.split()).lower()


def _contains_fraction(tracked: Doc, sections) -> float:
    """Fraction of `sections` whose wording appears in the tracked copy's text.

    Compared against the tracked copy's whole text rather than clause by clause,
    because the marked-up copy renumbers nothing and a clause that moved would
    otherwise read as absent.
    """
    haystack = _squash(tracked.text)
    if not haystack or not sections:
        return 0.0
    hits = 0
    for section in sections:
        body = _squash(section.body)
        # Match on an opening run of words: MAS's markup interleaves struck-through
        # wording mid-clause, so a whole clause body is rarely contiguous.
        probe = " ".join(body.split()[:12])
        if len(probe) >= 25 and probe in haystack:
            hits += 1
    return hits / len(sections)


def measure_pair(spec, assignment, old: Doc, new: Doc, verbose: bool) -> dict:
    """Score one consecutive pair of clean consolidated versions.

    Two conditions have to hold before a number is produced.

    First, MAS must have published a tracked copy *of this revision* — see
    `assign_tracked`, which decides that from MAS's documents alone.

    Second, the markup must cover the whole interval. A clause present in `new` and
    absent from `old` must appear in the tracked copy as an insertion; if it does not,
    the two versions are separated by a round the markup says nothing about. Notice 314
    is why this test exists: its last two clean versions are April 2015 and March 2022
    with three amendment rounds between them, and scored against the 2022 markup alone
    the differ looked 47.5% wrong. Spot-checked, every one of those "false positives"
    was a genuine change made in a round that markup does not describe.

    An unmeasurable pair is a gap in what we can prove, not evidence the differ is
    wrong, and the two must never be pooled together.
    """
    label = f"{old.date} -> {new.date}"
    old_sections = parse_pdf(old.path)
    new_sections = parse_pdf(new.path)
    old_keys = {s.section_key for s in old_sections}
    new_keys = {s.section_key for s in new_sections}

    best, best_score = assignment.get(id(new), (None, 0.0))
    if best is None:
        return {"ref": spec.external_ref, "pair": label,
                "skip": "MAS published no tracked copy of this revision"}

    marked, _ = changed_clauses(best.path)
    truth = {k for k in marked if not k.startswith("Footnote")}
    if not truth:
        return {"ref": spec.external_ref, "pair": label,
                "skip": "tracked copy carries no extractable markup"}

    unmarked_new = (new_keys - old_keys) - truth
    if unmarked_new:
        return {"ref": spec.external_ref, "pair": label,
                "skip": f"markup does not cover the whole interval — "
                        f"{len(unmarked_new)} clause(s) new in this version are not "
                        f"marked as insertions ({', '.join(sorted(unmarked_new)[:5])}"
                        f"{'...' if len(unmarked_new) > 5 else ''})"}

    deltas = compute_delta(old_sections, new_sections)
    reported = {d.new_section_key or d.old_section_key for d in deltas}
    tp, fp, fn = reported & truth, reported - truth, truth - reported

    if verbose:
        print(f"      tracked: {slug(best.url)}  (match {best_score:.0%})")

    return {
        "ref": spec.external_ref, "pair": label,
        "round": str(new.date.year),
        "parsed": len(new_sections),
        "truth": len(truth), "reported": len(reported),
        "fp": sorted(fp), "fn": sorted(fn),
        "precision": len(tp) / len(reported) if reported else 0.0,
        "recall": len(tp) / len(truth),
        "fp_rate": len(fp) / len(reported) if reported else 0.0,
    }


def assign_tracked(docs: list[Doc], clean: list[Doc]) -> dict[int, tuple[Doc, float]]:
    """Map each clean version to the tracked copy that marks it up, if there is one.

    Decided from MAS's documents alone — never from our own diff, which would let the
    measurement pick whichever pairing it happens to score well on.

    A marked-up copy of revision R has R's clause tree, so clause-key overlap
    identifies R almost every time: Notice 626's 2025 markup carries 146 clause keys
    and so does the 2025 clean copy, against 142 in the 2024 one. Where two clean
    versions share a clause tree — 626's 2022 and 2024 copies both parse to 142 — the
    tie is broken on wording: the 2022 markup contains the 2022 text as insertions and
    does not contain 2024's later edits.

    A tracked copy that matches nothing well enough is dropped rather than forced onto
    the nearest version.
    """
    out: dict[int, tuple[Doc, float]] = {}
    for doc in docs:
        if not (doc.tracked and doc.consolidated):
            continue
        keys = {s.section_key for s in doc.sections}
        scored = []
        for version in clean:
            vkeys = {s.section_key for s in version.sections}
            union = keys | vkeys
            scored.append((version, len(keys & vkeys) / len(union) if union else 0.0))
        best = max(score for _, score in scored)
        if best < 0.90:
            continue
        tied = [v for v, score in scored if best - score <= 0.02]
        target = (tied[0] if len(tied) == 1
                  else max(tied, key=lambda v: _contains_fraction(doc, v.sections)))
        if id(target) not in out or best > out[id(target)][1]:
            out[id(target)] = (doc, best)
    return out


def measure(spec, docs: list[Doc], verbose: bool) -> list[dict]:
    """Every consecutive pair of clean versions that can be scored honestly."""
    clean = sorted((d for d in docs if d.consolidated and not d.tracked and d.date),
                   key=lambda d: d.date)
    if len(clean) < 2:
        return [{"ref": spec.external_ref, "pair": "-",
                 "skip": "fewer than two dated clean consolidated versions"}]
    assignment = assign_tracked(docs, clean)
    return [measure_pair(spec, assignment, old, new, verbose)
            for old, new in itertools.pairwise(clean)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=str(ROOT / ".cache" / "mas-pdfs"))
    ap.add_argument("--only", action="append", help="external_ref; repeatable")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    client = PoliteClient(min_interval_seconds=2.0)

    specs = MAS_INSTRUMENTS
    if args.only:
        specs = tuple(s for s in specs if s.external_ref in set(args.only))

    results: list[dict] = []
    for spec in specs:
        print(f"\n=== {spec.external_ref} ===")
        docs = fetch_all(client, spec, cache, args.verbose)
        print(f"    {len(docs)} PDFs parsed")
        for result in measure(spec, docs, args.verbose):
            results.append(result)
            if "skip" in result:
                print(f"    {result['pair']}: not measurable — {result['skip']}")
                continue
            print(f"    {result['pair']}  ({result['parsed']} clauses)  "
                  f"MAS marked {result['truth']}, we report {result['reported']}")
            print(f"      precision {result['precision']:.1%} | "
                  f"recall {result['recall']:.1%} | "
                  f"FP rate {result['fp_rate']:.1%}  [gate <{GATE:.0%}]")
            if result["fp"]:
                print(f"      false positives: {result['fp']}")
            if result["fn"]:
                print(f"      false negatives: {result['fn']}")

    measured = [r for r in results if "skip" not in r]
    print("\n" + "=" * 78)
    print(f"{'instrument':<13}{'round':<10}{'parsed':>7}{'MAS':>5}{'ours':>6}"
          f"{'prec':>8}{'recall':>8}{'FP rate':>9}")
    for r in measured:
        print(f"{r['ref']:<13}{r['round']:<10}{r['parsed']:>7}{r['truth']:>5}"
              f"{r['reported']:>6}{r['precision']:>8.1%}{r['recall']:>8.1%}"
              f"{r['fp_rate']:>9.1%}")

    if not measured:
        print("\nNothing measurable.")
        return 1

    reported = sum(r["reported"] for r in measured)
    truth = sum(r["truth"] for r in measured)
    fps = sum(len(r["fp"]) for r in measured)
    tps = reported - fps
    pooled_fp = fps / reported if reported else 0.0
    print("-" * 78)
    print(f"{'POOLED':<13}{'':<10}{'':>7}{truth:>5}{reported:>6}"
          f"{tps / reported:>8.1%}{tps / truth:>8.1%}{pooled_fp:>9.1%}")

    instruments = {r["ref"] for r in measured}
    print(f"\n{len(measured)} version pair(s) across {len(instruments)} instrument(s): "
          f"{', '.join(sorted(instruments))}")
    worst = max(measured, key=lambda r: r["fp_rate"])
    print(f"worst pair: {worst['ref']} {worst['pair']} at {worst['fp_rate']:.1%} "
          f"false positives")

    unmeasurable = [r for r in results if "skip" in r]
    if unmeasurable:
        print(f"\n{len(unmeasurable)} pair(s) not measurable:")
        for r in unmeasurable:
            print(f"  {r['ref']:<13}{r['pair']:<26}{r['skip']}")
    return 0 if pooled_fp < GATE else 1


if __name__ == "__main__":
    raise SystemExit(main())
