# Differ accuracy across the corpus

Measured 26 August 2026. Reproduce with:

```bash
.venv/bin/python scripts/measure_parse_quality.py
```

The G1 figure in [threshold-tuning.md](threshold-tuning.md) was measured on Notice 626
alone. This is the same measurement run over all eleven instruments.

## Result

| Instrument | Round | Clauses parsed | MAS marked | We report | Precision | Recall | FP rate |
|---|---|---:|---:|---:|---:|---:|---:|
| Notice 626 | 2025 | 146 | 17 | 16 | 100.0% | 94.1% | **0.0%** |
| FAA-N06 | 2022 | 107 | 36 | 34 | 97.1% | 91.7% | **2.9%** |
| TCA-N03 | 2022 | 101 | 36 | 34 | 94.1% | 88.9% | **5.9%** |
| PSN01 | 2025 | 169 | 18 | 18 | 94.4% | 94.4% | **5.6%** |
| PSN02 | 2025 | 159 | 17 | 17 | 100.0% | 100.0% | **0.0%** |
| **Pooled** | | | **124** | **119** | **96.6%** | **92.7%** | **3.4%** |

**Pooled false-positive rate 3.4%, against a gate of 5%.** Five instruments, five
revision rounds, 119 reported changes.

Two instruments are individually over the gate, and the honest reading is that the
samples are small: TCA-N03's 5.9% is 2 false positives out of 34, PSN01's 5.6% is 1 out
of 18. One more or fewer moves either figure by three points. Three of the four are in
`Appendix 2`, where clause numbering restarts and collides with the main body's.

Every false negative is a clause MAS marked that we did not report; none is a change
reported wrongly. In a compliance product a miss is worse than noise, so these are the
ones worth attention — but at 92.7% pooled recall they are the exception.

## What can and cannot be measured

The ground truth is MAS's own tracked-changes PDF: a clause carrying coloured
characters is a clause MAS marked as amended. That only works where MAS published such
a copy, and where its markup covers the whole gap between the two clean versions being
compared. Of 61 consecutive version pairs across the corpus, **5 satisfy both**.

The reasons the other 56 do not:

| Reason | Pairs |
|---|---|
| MAS published no tracked copy of that revision | 44 |
| Markup covers only part of the interval | 6 |
| Tracked copy's markup is not attributable to a clause | 5 |
| Fewer than two dated clean versions | 1 |

**A pair we cannot measure is a gap in what we can prove, not evidence the differ is
wrong.** Keeping those two apart is the whole point of the script, and it is not a
theoretical concern:

- Notice 314's last two clean versions are April 2015 and March 2022, with amendment
  rounds in Nov 2015, June 2021 and March 2022 in between. MAS published tracked copies
  for the last two. Scored against those, the differ looks **47.5% wrong**. Every one of
  those "false positives" that was spot-checked (7.1, 8.2, 10.1, 12.1, 13.6) is a real
  textual change made in a round the markup does not describe. The differ is right and
  the oracle is incomplete.
- The script now refuses to score such a pair: a clause present in the newer version and
  absent from the older one must appear in the tracked copy as an insertion, or the
  interval is declared unmeasurable.

## Two things found while doing this

**1. The oracle only recognised pure red.** Notice 626's 2025 tracked copy marks changes
in `(1, 0, 0)`; Notice 314's uses crimson `(0.71, 0.03, 0.18)` and some blue. Hard-coding
pure red made 314 read as a document with nothing marked in it, which scores as 0% recall
rather than as the bug it is. The test is now "chromatic" — black, white and greys have
equal RGB components and every markup colour seen so far does not. Notice 626's G1
numbers are unchanged by this.

**2. The June 2021 markup for four instruments is not attributable to a clause.**
FAA-N06, TCA-N03, SFA13-N01 and SFA04-N02 all have a June 2021 tracked copy carrying
~430 coloured characters, and the oracle extracts nothing from any of them. The markup
is real and substantive — definitions of "bank" and "stored value facility" changed,
`administrated` became `administered` — but it sits in the **unnumbered definitions
block and the endnotes**, which the parser does not attach to a numbered clause key.

Whether the differ *reports* those changes is a separate open question. Spot-checking
FAA-N06, the 2021 definition wording is parsed into clause `8.8`'s body, which suggests
mis-attribution rather than a silent miss — but that is a suspicion, not a measurement.
Worth resolving before anyone claims definition changes are covered.

## Method

1. Fetch every PDF linked from each instrument's MAS landing page (cached; 2s apart).
2. Classify each with the pipeline's own `classify()` — consolidated, tracked, or
   neither — so the measurement and production cannot drift apart.
3. Assign each tracked copy to the revision it marks up, by clause-key overlap, with
   wording containment breaking ties between versions that share a clause tree.
   **Decided from MAS's documents only** — a matcher that consulted our own diff would
   pick whichever pairing we score well on, and the number would mean nothing.
4. For each consecutive pair of clean versions, run `compute_delta` and score against
   the assigned tracked copy, after the coverage test above.

Footnotes are excluded, matching the shipping default (`include_footnotes=False`).
