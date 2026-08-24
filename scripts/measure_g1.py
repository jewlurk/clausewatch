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


def main() -> int:
    truth, _ = changed_clauses(FIXTURES / "626_2025_tracked.pdf")
    old = parse_pdf(FIXTURES / "626_2024.pdf")
    new = parse_pdf(FIXTURES / "626_2025.pdf")
    deltas = compute_delta(old, new)

    reported = {d.new_section_key or d.old_section_key for d in deltas}
    true_positives = reported & truth
    false_positives = reported - truth
    false_negatives = truth - reported

    fp_rate = len(false_positives) / len(reported) if reported else 0.0
    print(f"clauses in 2025 doc : {len(new)}")
    print(f"MAS says changed    : {len(truth)}")
    print(f"we report changed   : {len(reported)}")
    print(f"  true positives    : {len(true_positives)}")
    print(f"  FALSE POSITIVES   : {len(false_positives)}  {sorted(false_positives)}")
    print(f"  false negatives   : {len(false_negatives)}  {sorted(false_negatives)}")
    print()
    print(f"precision           : {len(true_positives) / len(reported):.1%}")
    print(f"recall              : {len(true_positives) / len(truth):.1%}")
    print(f"FALSE POSITIVE RATE : {fp_rate:.1%}   [G1 target < 5%]")

    return 0 if fp_rate < 0.05 else 1


if __name__ == "__main__":
    raise SystemExit(main())
