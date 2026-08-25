# Project state — Clausewatch

Written so a fresh session (or a compacted one) can pick up without re-deriving
anything. Updated 25 August 2026.

---

## Where things stand

| Gate | Status |
|---|---|
| G1 — differ under 5% false positives | **Met.** 0% FP, 100% precision, 94.4% recall, measured against MAS's own tracked-changes PDF. Reproduce: `.venv/bin/python scripts/measure_g1.py` |
| G2 — public demo asset | **Met.** https://jewlurk.github.io/clausewatch/ |
| G3 — 20 firms contacted | **Founder task, not started.** The bottleneck. |
| G4 — first design partner | Product is ready enough; needs G3 first. |

**Live corpus:** 11 MAS AML/CFT notices, 127 documents, 64 versions, 1,918 clause
changes. Pipeline runs daily at 01:17 UTC (~09:17 SGT) and redeploys itself.

## Live URLs

- Public changelogs — https://jewlurk.github.io/clausewatch/
- Customer console — https://jewlurk.github.io/clausewatch/app.html
- User guide — https://jewlurk.github.io/clausewatch/guide.html
- Repo — https://github.com/jewlurk/clausewatch

## Infrastructure

| Piece | Where | Notes |
|---|---|---|
| Database | Supabase `psppoaswytqhkdqbudnv`, **Singapore** | Free tier, ~5MB of 500MB used |
| Raw PDFs | Cloudflare R2 `clausewatch-raw`, APAC, **private** | ~40MB of 10GB |
| Pipeline | GitHub Actions `daily.yml` | Public repo, unlimited minutes |
| Site | GitHub Pages (**not** Cloudflare Pages — see decisions) | |
| LLM | Anthropic `claude-haiku-4-5` | ~USD 0.35 spent to date |

GitHub secrets in use: `DATABASE_URL` (session pooler), `R2_ACCESS_KEY_ID`,
`R2_SECRET_ACCESS_KEY`, `ANTHROPIC_API_KEY`.

## Hard-won gotchas — do not rediscover these

1. **MAS blocks bare bot user-agents** with an HTTP 200 "Maintenance" page, not a 4xx.
   The UA must start with `Mozilla/5.0`. `crawler/http.py` detects the block page,
   because status alone cannot be trusted.
2. **Supabase direct connections are IPv6-only**; GitHub Actions has no IPv6. Use the
   **session pooler** host (`aws-0-ap-southeast-1.pooler.supabase.com`), user
   `postgres.<ref>`. A direct URL fails as a confusing timeout.
3. **Postgres refuses to change a function's return type in place** — `drop function`
   first in any migration that alters a signature.
4. **RLS off ≠ safe.** Supabase grants anon full DML by default; RLS is what withholds
   it. Migration 0002 exists because the publishable key could once delete the corpus.
5. **PDF parsing:** use `LAParams(boxes_flow=None)` or sub-item labels detach from their
   text. Clause numbers often sit alone on a line with the body beneath. MAS inserts
   `6.14A`–`6.14D` rather than renumbering. Footnote markers concatenate onto
   references (`11.5` + footnote `5` = `11.55`) — filtered by font size.
6. **Two `matched` sets in the differ.** Old and new clause keys share a namespace; one
   set silently drops a renumbered run. See `diff/delta.py`.
7. **Instrument metadata must be read from MAS, never constructed.** Notice 626A binds
   credit/charge card licensees, not merchant banks (that is 1014). SFA13-N01 lives at
   `notice-sfa-13-n01`.

## Decisions that look odd without the reason

- **No API server.** The brief specifies Hono on Workers. RLS enforces isolation at the
  database and corpus reads go through capped `security definer` functions, so a Worker
  would add a hop without adding a guarantee.
- **GitHub Pages, not Cloudflare Pages.** Needed no extra credential, so the demo was
  not blocked. The HTML is static; moving is a deploy-step change.
- **Scope is AML/CFT only.** The 0% false-positive figure was measured on notices.
  Codes, Guidelines and Practice Notes are structured differently and unmeasured.
- **Footnotes parsed but off by default.** They add 1.6 points of recall and cost 27
  points of precision. `parse_pdf(..., include_footnotes=True)` enables them.
- **Undated versions are excluded from timelines**, not sorted last — an undated version
  placed arbitrarily produces a diff between versions that may not be adjacent.
- **Cancelled notices excluded** (3001, PSOA-N02). Following a dead notice is worse than
  not covering it.

## Known gaps

- **T26 email alerts do not exist.** The site updates; nobody is told.
- ~1,500 of 1,918 changes lack summaries — batch capped at 400/run, fills in over days.
- Parse quality on the 6 newest instruments is **unmeasured**; the 0% figure is Notice
  626 only. Do not quote it as covering all eleven.
- Footnote-only changes are missed. Disclosed in the Terms.
- `trgm_best_match` (T16) is still in-memory Python, not SQL over the GIN index.
- Some versions have no extractable date and are dropped from timelines.

## Verification commands

```bash
.venv/bin/python scripts/measure_g1.py        # differ accuracy vs MAS's own document
cd ingest && ../.venv/bin/python -m pytest -q # 92 tests
```

Workflow `crawl.yml` has manual flags: `check_r2`, `check_db`, `check_rls`,
`backfill_626` (all instruments), `build_corpus`, `migration`.

## Legal position — load-bearing, do not weaken

- **Descriptive only.** Legal Profession Act 1966 s.33 makes advising on legal
  obligations a criminal offence for the unqualified. The LLM prompt forbids
  interpretation *and* `enrich/summarise.py` filters the output — a prompt is a request,
  not a guarantee.
- **Never republish the corpus.** Only changed clauses, as excerpts, capped at 40% of an
  instrument per comparison, always deep-linked to MAS.
- Drafts in `docs/legal/` are **unreviewed by a lawyer** and must be before taking money.
