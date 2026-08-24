"""G1 measurement: our differ vs MAS's own tracked-changes document.

Run from the repo root:   .venv/bin/python scripts/measure_g1.py
Results and interpretation: docs/threshold-tuning.md
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ingest"))
sys.path.insert(0, str(ROOT / "scripts"))

from diff.delta import compute_delta
from mas_tracked_oracle import changed_clauses
from parse.sections import parse_pdf

FIXTURES = ROOT / "ingest" / "tests" / "fixtures"


def run(truth: set[str], include_footnotes: bool) -> float:
    old = parse_pdf(FIXTURES / "626_2024.pdf", include_footnotes=include_footnotes)
    new = parse_pdf(FIXTURES / "626_2025.pdf", include_footnotes=include_footnotes)
    deltas = compute_delta(old, new)

    scope = truth if include_footnotes else {k for k in truth if not k.startswith("Footnote")}
    reported = {d.new_section_key or d.old_section_key for d in deltas}
    true_positives = reported & scope
    false_positives = reported - scope
    false_negatives = scope - reported

    fp_rate = len(false_positives) / len(reported) if reported else 0.0
    label = "WITH footnotes" if include_footnotes else "clauses only (shipping default)"
    print(f"--- {label} ---")
    print(f"  sections parsed   : {len(new)}")
    print(f"  MAS says changed  : {len(scope)}")
    print(f"  we report changed : {len(reported)}")
    print(f"  FALSE POSITIVES   : {len(false_positives)}  {sorted(false_positives)}")
    print(f"  false negatives   : {len(false_negatives)}  {sorted(false_negatives)}")
    print(f"  precision {len(true_positives) / len(reported):.1%} | "
          f"recall {len(true_positives) / len(scope):.1%} | "
          f"FP rate {fp_rate:.1%}  [gate <5%]")
    print()
    return fp_rate


def main() -> int:
    truth, _ = changed_clauses(FIXTURES / "626_2025_tracked.pdf")
    shipping_fp_rate = run(truth, include_footnotes=False)
    run(truth, include_footnotes=True)
    return 0 if shipping_fp_rate < 0.05 else 1


if __name__ == "__main__":
    raise SystemExit(main())
