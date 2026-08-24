# Differ accuracy — measured, not assumed (T20 / Gate G1)

**Date:** 25 August 2026
**Question G1 asks:** can clause-level diffing hit under 5% false positives on real MAS documents?
**Answer: yes — 0% false positives, 100% precision, 94.4% recall on the measured pair.**

## How this was measured

Most "accuracy" claims about diffing are circular: the differ is compared against
itself. This one is not. MAS publishes its own tracked-changes document for the
30 June 2025 amendment
(`mas-notice-626---amendment-notes-june-2025.pdf`), which states it is compared against
the 28 March 2024 version — exactly our diff pair.

In that PDF, changed text is coloured red (struck through for deletions, underlined for
insertions). Extracting the document twice — once with all characters, once with red
characters omitted — and comparing per section yields **MAS's own list of changed
sections**, independent of our code: **25 sections** (18 clauses + 7 footnotes).

The oracle covers footnotes as well as clauses. An earlier version did not, and scored
every real footnote amendment as a false positive — which understated clause-level
recall at 77% when the true figure was 94.4%. Measure the same units you report.

Reproduce with `scripts/measure_g1.py`.

## Result

Both modes are measured on every run. Clause-only is what ships.

| | Clauses only (**shipping**) | With footnotes |
|---|---|---|
| Sections parsed | 146 | 162 |
| MAS says changed | 18 | 25 |
| We report | 17 | 33 |
| **False positives** | **0 (0.0%)** ✅ | 9 (27.3%) |
| Precision | **100%** | 72.7% |
| Recall | **94.4%** | 96.0% |

### The one real miss

Para **6.24**. Its extracted text is byte-identical between the 2024 and 2025 PDFs with
*and* without footnotes, yet MAS coloured it in the tracked document — the change is
invisible to text extraction (formatting, or colour applied to unchanged text). Not
currently detectable by any text-based differ.

### Footnotes: why they are off by default

Footnotes carry real amendments — the June 2025 round renumbered cross-references from
`11A.x` to `11.x` inside footnote text — and enabling them lifts recall 94.4% → 96.0%.
They are parsed and available (`parse_pdf(..., include_footnotes=True)`), keyed
`Footnote N`, so footnote renumbering is absorbed by the differ's existing RENUMBERED
path rather than smearing across every clause that cites them.

They are **off by default** because they also take the false-positive rate from 0% to
27.3%. The residual noise is sub-item labels (`(a)`/`(c)`) reordering under PDF column
extraction — an extraction-stability problem, not a differ fault. Nine noisy alerts to
recover 1.6 points of recall is the wrong trade for a product whose value is trust.

**Next task on this:** stabilise footnote sub-item extraction, then turn footnotes on
and re-measure. Until then, the product does not alert on footnote-only changes, and
that limitation should be stated plainly to design partners rather than discovered.

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
- **Footnotes parsed but off by default.** Buys the 0% false-positive rate at the cost
  of not alerting on footnote-only changes. Revisit once sub-item extraction is stable.
- **Section granularity is the decimal clause** (`6.14`), not sub-items (`6.14(a)(i)`).

## Caveat

One instrument, one version pair. Before treating G1 as settled the same measurement
should run on PSN01/PSN02 and SFA04-N02, which have their own tracked-changes documents
from the same 30 June 2025 amendment round.
