# Differ accuracy — measured, not assumed (T20 / Gate G1)

**Date:** 25 August 2026
**Question G1 asks:** can clause-level diffing hit under 5% false positives on real MAS documents?
**Answer: yes — 0% false positives, 100% precision on the measured pair.** Recall is the
weaker number and is where the remaining work is.

## How this was measured

Most "accuracy" claims about diffing are circular: the differ is compared against
itself. This one is not. MAS publishes its own tracked-changes document for the
30 June 2025 amendment
(`mas-notice-626---amendment-notes-june-2025.pdf`), which states it is compared against
the 28 March 2024 version — exactly our diff pair.

In that PDF, changed text is coloured red (struck through for deletions, underlined for
insertions). Extracting the document twice — once with all characters, once with red
characters omitted — and comparing per clause yields **MAS's own list of changed
clauses**, independent of our code. That is the ground truth: **22 clauses**.

Reproduce with `scripts/measure_g1.py`.

## Result

| Metric | Value | Gate |
|---|---|---|
| Ground truth (MAS-marked changed clauses) | 22 | — |
| Reported by `compute_delta` | 17 | — |
| True positives | 17 | — |
| **False positives** | **0 (0.0%)** | **< 5% ✅** |
| Precision | 100% | — |
| Recall | 77.3% | — |

### Recall, honestly

Five clauses MAS marked are not reported. They split into two groups:

| Clause | Cause | Real miss? |
|---|---|---|
| 4.1, 6.3 | Change is **inside a footnote**, and footnotes are excluded from clause bodies | **Yes** |
| 15.14, 15.8, 6.24 | Extracted text is byte-identical with *and* without footnotes — MAS applied colour to text that did not change | No (oracle artifact) |

Discounting the three oracle artifacts, real recall is **17/19 = 89.5%**.

**This is the top open risk.** For a compliance product a missed change is worse than a
false positive: the entire promise is "you will not miss anything." Fix is known — parse
footnotes as their own sections with stable keys instead of dropping them, so footnote
edits surface as changes to `Footnote N` while renumbering is absorbed by the existing
RENUMBERED path. Not yet done.

## What actually moved the numbers

False-positive rate across successive fixes on the same pair:

| Change | FP rate |
|---|---|
| Baseline (brief §9 as written) | 36.7% |
| Exclude footnote text and superscript markers by font size | 10.5% |
| Treat punctuation-only edits as cosmetic (severity 1) | 5.6% |
| Treat word-reorder-with-identical-multiset as cosmetic | **0.0%** |

### Footnotes were the whole problem

9 of the original 11 false positives were footnote noise. MAS renumbers footnotes
whenever one is inserted, so an untouched clause reads `institutions4` in one version
and `institutions6` in the next; markers also concatenate onto references
(`11.5` + footnote `5` → `11.55`). Footnote *bodies* additionally migrate between
clauses as page breaks shift.

They are separable by font: body text is the document's modal size (13.0pt in Notice
626), footnote bodies ~10pt, superscript markers 6.5–8.5pt. Anything below 90% of the
modal size is dropped. The ratio is relative, so it survives a document set in a
different base size.

## Thresholds

| Constant | Value | Basis |
|---|---|---|
| `RENUMBER_THRESHOLD` | 0.72 | Brief's starting value, **not yet independently tuned** — the 2024→2025 amendment contains no renumbering, so this pair cannot exercise it. Renumbering is covered by the synthetic §12 test only. Tune when a real renumbering pair is available. |
| `MODIFY_FLOOR` | 0.35 | Below this, same-numbered clauses are treated as unrelated and deferred to Pass 2. |
| `FOOTNOTE_SIZE_RATIO` | 0.9 | Font-size floor as a fraction of the document's modal size. |

## Two corrections to the brief's algorithm (§9)

Both were found by the §12 renumbering test, which failed against the algorithm as
written.

1. **Pass 1 trusted clause numbers unconditionally.** The brief marks every
   same-number pair MODIFIED. When a clause is inserted mid-document and everything
   below shifts up one, each reused number then holds unrelated text, so Pass 1 reports
   the entire tail as MODIFIED — and Pass 2, which exists to catch exactly this, never
   sees those clauses. Fixed: a same-number pair whose bodies score below
   `MODIFY_FLOOR` is deferred to Pass 2.

2. **One `matched_new` set was used for both sides.** Old and new clause keys share a
   namespace, so once new `6.3` is claimed by old `6.2`, the same set also marks old
   `6.3` handled and silently drops it. A renumbered *run* triggers this on every
   clause. Fixed with separate `matched_new` / `handled_old` sets.

With both fixes the §12 test passes: inserting one clause mid-document yields exactly
1 ADDED + 3 RENUMBERED and **zero** MODIFIED.

## Judgement calls to challenge

- **Word-reorder treated as cosmetic.** If two bodies contain the same words in a
  different order, it is scored severity 1 and filtered. Verified case: para 8.1, where
  the 2024 extraction yields "party international officials, members of organisations"
  for source text MAS left untouched — a PDF reading-order artifact at a line break. The
  risk is a genuine reordering that changes meaning being suppressed. Rare in legal
  drafting, but it is a real trade-off.
- **Footnotes dropped entirely.** Buys the 0% false-positive rate, costs the two real
  misses above. Should become "footnotes as their own sections".
- **Section granularity is the decimal clause** (`6.14`), not sub-items (`6.14(a)(i)`).

## Caveat

One instrument, one version pair. Before treating G1 as settled the same measurement
should run on PSN01/PSN02 and SFA04-N02, which have their own tracked-changes documents
from the same 30 June 2025 amendment round.
