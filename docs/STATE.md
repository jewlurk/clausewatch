# Project state — Clausewatch

Written so a fresh session (or a compacted one) can pick up without re-deriving
anything. Updated 26 August 2026.

---

## Where things stand

| Gate | Status |
|---|---|
| G1 — differ under 5% false positives | **Met, and now measured beyond one instrument.** Notice 626: 0% FP, 100% precision, 94.1% recall. Pooled across 5 instruments and 119 changes: **3.4% FP**, 96.6% precision, 92.7% recall. Reproduce: `scripts/measure_g1.py` and `scripts/measure_parse_quality.py`. Scope and caveats: [parse-quality.md](parse-quality.md) |
| G2 — public demo asset | **Met.** https://jewlurk.github.io/clausewatch/ |
| G3 — 20 firms contacted | **Deliberately deferred until the build is finished.** See sequencing below. |
| G4 — first design partner | Follows G3. |

**Live corpus:** 11 MAS AML/CFT notices, 127 documents, 64 versions, 1,918 clause
changes. Pipeline runs daily at 01:17 UTC (~09:17 SGT) and redeploys itself.

## Sequencing — founder decision, 25 August 2026

**Finish the build first. Send outreach after.** Target: all building complete within
two days of this date, then G3.

The reasoning, in the founder's words: sending a link to a site with unverified
features and unknown bugs is pointless — a compliance buyer who finds a defect on
first contact is not a buyer you get a second try at. The project started ~23 August
and the outer deadline is 1 April 2027, so there is time to do it in the right order.

**Do not keep pressing for outreach before the build is done.** The trade-off was
raised, considered, and decided. Treat G3 as scheduled, not as neglected.

### Remaining build work, in order

1. ~~**Verification pass**~~ — **done 26 Aug 2026.** `scripts/verify_console.py` replays
   every call `web/app.html` makes against the live database with RLS enforced; 43
   checks, all passing. Public pages, links and mobile widths checked in a browser.
   Found and fixed: literal `\u2190` rendering as text on the live site, and
   `generate_alerts()` raising on every call. Not covered: Supabase's magic-link
   delivery, which needs a mailbox.
2. ~~**T26 email alerts**~~ — **built and verified against live data 26 Aug 2026**, but
   **cannot send until there is a domain**. Resend requires a verified sending domain;
   there is no domainless send path. See "The domain is now a blocker" below.
3. **Finish the summaries** — batch size is now `ENRICH_BATCH` (default 400); dispatch
   `crawl.yml` with `enrich_batch` to clear the backlog.
4. ~~**Measure parse quality on the other instruments**~~ — **done 26 Aug 2026.** Pooled
   3.4% false positives over 5 instruments / 119 changes, against the 5% gate. Full
   table, method and caveats: [parse-quality.md](parse-quality.md). Note STATE.md was
   wrong about this: only 626, PSN01 and PSN02 have 2025 tracked copies.
5. **Investigate undated versions** dropped from timelines (see Known gaps).
6. **Demote trivial changes** — punctuation and word-order edits still surface with the
   same weight as substantive ones. Summaries now exist, so ranking can use them.
7. **Definitions-block changes may be mis-attributed.** The June 2021 markup for four
   instruments sits in the unnumbered definitions block; spot-checking FAA-N06, that
   wording lands in clause 8.8's body. Suspicion, not a measurement — resolve before
   claiming definition changes are covered. See [parse-quality.md](parse-quality.md).
8. Optional, in value order: Guidelines coverage (they change more often than the
   notices), T16 SQL trigram matcher, T29 cost guardrails, T31 schema-drift detection,
   T32 restore drill, T34 vendor security pack.

### The domain is now a blocker, not a preference

Resend's documentation, checked 26 August 2026: "You must add and verify at least one
domain to send emails with Resend." Free tier is 100 emails/day, 3,000/month, 3 domains.

TODO.md parked the domain as a judgement call about how outreach looks. It is no longer
that: **T26 does not deliver a single email without one.** Cost is SGD 15-25/year against
a budget cap of SGD 0 until Feb 2027, so it needs the founder's explicit call — but the
thing being bought is the alerting half of the product, not a nicer-looking link.

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
`R2_SECRET_ACCESS_KEY`, `ANTHROPIC_API_KEY`. Not yet set: `RESEND_API_KEY` (secret)
and `ALERT_FROM` (repo variable), which T26 needs.

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
7. **A tracked-changes copy carries the *previous* revision's date in black.** So the
   date parsed out of one is the wrong date — Notice 314's June 2021 markup parses as
   30 November 2015. Match a tracked copy to its revision by clause-key overlap, never
   by date. `scripts/measure_parse_quality.py` does this.
8. **MAS's markup colour is not always red.** 626 uses `(1,0,0)`; 314 uses crimson
   `(0.71,0.03,0.18)`. The oracle tests for any chromatic colour.
9. **`select distinct ... null` types the NULL as `text`.** That is what kept
   `generate_alerts()` broken and undetected from creation until 26 Aug 2026: it raised
   on every call, and nothing called it. Cast it — `null::bigint`.
10. **A unique index treats NULLs as distinct**, so `on conflict` cannot dedupe rows
   with a null column. `alerts_dedup_idx` is `nulls not distinct` (migration 0006).
11. **Instrument metadata must be read from MAS, never constructed.** Notice 626A binds
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

- **T26 alerts cannot send until a domain exists** (above). The code is built, tested
  and verified against live data; only the transport is blocked.
- Summaries: backlog clears via `crawl.yml` -> `enrich_batch`.
- Accuracy is measured on **5 of 11 instruments and 5 of 61 version pairs** — that is
  every pair MAS published usable markup for, not a sampling choice. Quote 3.4% pooled
  with that scope attached, never as "all eleven instruments".
- Footnote-only changes are missed. Disclosed in the Terms.
- Changes inside the unnumbered definitions block may be attached to the wrong clause.
- `trgm_best_match` (T16) is still in-memory Python, not SQL over the GIN index.
- Some versions have no extractable date and are dropped from timelines.

## Verification commands

```bash
.venv/bin/python scripts/measure_g1.py             # Notice 626 vs MAS's own markup
.venv/bin/python scripts/measure_parse_quality.py  # the same test, whole corpus
cd ingest && ../.venv/bin/python -m pytest -q      # 107 tests
```

The console cannot be verified locally — `DATABASE_URL` only exists in Actions. Dispatch
`crawl.yml` with `check_console` (every path `app.html` uses, under RLS), `check_rls`
(T22 isolation) or `send_alerts_dry_run` (renders the T26 emails from live data, sends
nothing).

Workflow `crawl.yml` has manual flags: `check_r2`, `check_db`, `check_rls`,
`check_console`, `enrich_batch`, `send_alerts_dry_run`, `backfill_626` (all
instruments), `build_corpus`, `migration`.

## Legal position — load-bearing, do not weaken

- **Descriptive only.** Legal Profession Act 1966 s.33 makes advising on legal
  obligations a criminal offence for the unqualified. The LLM prompt forbids
  interpretation *and* `enrich/summarise.py` filters the output — a prompt is a request,
  not a guarantee.
- **Never republish the corpus.** Only changed clauses, as excerpts, capped at 40% of an
  instrument per comparison, always deep-linked to MAS.
- Drafts in `docs/legal/` are **unreviewed by a lawyer** and must be before taking money.
