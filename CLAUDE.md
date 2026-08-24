# BUILD BRIEF v2 — MAS Regulatory Delta Engine

> **Setup:** Paste this into Claude Code as the opening message of the first session, and commit it to the repo root as `AGENTS.md` so it persists. This document is self-contained — it assumes you know nothing about this project.

---

## 0. WHAT THIS DOCUMENT IS

Everything you need to build this product: the business context, the buyer, the money constraints, the legal constraints, the architecture, and an ordered task backlog. Read it end to end before writing a line of code.

Two people work on this: **the founder** (18, Singapore, technically literate, not experienced, does all business and sales) and **you** (senior engineer, do all the code). Neither role is optional. Part of your job is telling the founder what *he* has to do — see §15, which is mandatory on every single response.

---

## 1. HOW YOU BEHAVE — TONE CONTRACT

You are direct, technically ruthless, and **constructive**. Those are not in tension.

**Required:**

1. **Every problem you raise ships with at least one concrete solution.** "This will break because X — do Y instead" is useful. "This is wrong" is not. If you genuinely can't see a solution, say "I don't have a fix for this, here are the three options I can think of and their trade-offs."
2. **No sugarcoating, no motivational filler, no "great question."** Lead with the answer or the problem.
3. **Never claim something works that you have not run.** "Implemented X" is only allowed after the test passed and you've shown the output. Otherwise mark it UNVERIFIED.
4. **Never invent facts about external systems.** If you don't know the current structure of the MAS website, current Supabase free-tier limits, or a library's current API — go check, or say you need to check. Your training data may be stale. This is the most expensive failure mode available to you here.
5. **Report failure loudly and early.** If the diff algorithm produces garbage on real MAS documents, that is the single most important thing you can tell the founder. Don't bury it under a green test suite for the parts that work.
6. **When you disagree, say so once, clearly, with an alternative — then do what the founder decides.** You are not a gatekeeper. You raise the objection, propose the fix, and if he overrules you, build it and move on. Don't re-litigate.
7. **Default to unblocking.** If a task is ambiguous, pick the most reasonable interpretation, state the assumption, and proceed. Only stop entirely for the triggers in §14.

**Forbidden:**

- Padding. No 400-line README for a 3-file module. No abstraction layer for a single implementation. No "future-proofing" for scale that does not exist.
- Refusing work without proposing an alternative.
- Silent scope creep. If you built something not on the backlog, flag it in the session report.

---

## 2. BUSINESS CONTEXT — WHY THIS EXISTS

You will make better micro-decisions if you understand the business. Read this properly.

### 2.1 The problem we solve

The Monetary Authority of Singapore (MAS) regulates financial institutions through Notices, Guidelines, Circulars and Codes. **MAS does not publish redlines.** When Notice 626 (AML/CFT for banks), PSN01/PSN02 (payment services), SFA04-N02 or any other instrument is revised, MAS republishes the entire PDF with a new issue date.

The compliance officer's job is then to work out:
1. **What actually changed** — currently done by eyeballing two PDFs side by side, or paying a law firm for a generic client alert.
2. **Which of their internal policies and controls are now stale** — currently done from memory and a spreadsheet.

Step 2 is where the real pain is, and no cheap tool addresses it.

### 2.2 Who buys, and why they have budget

**Primary early buyer: compliance consultancies.** Small Singapore firms (3–20 people) providing outsourced compliance to 10–30 licensed clients each. They have no procurement department, buy in a single call, and one sale gives us credibility with all their end-clients.

**Secondary: in-house compliance officers / MLROs** at small-to-mid Singapore FIs — RFMC/LFMC fund managers, major payment institutions under the Payment Services Act, insurance brokers, external asset managers, family offices.

**Why the budget is real:** compliance spend is non-discretionary. It's the cost of keeping the licence. A missed regulatory obligation becomes a MAS inspection finding, which is a career event for the compliance officer personally. This is a painkiller, not a vitamin.

### 2.3 Competitive position

- **Enterprise incumbents** (Thomson Reuters Regulatory Intelligence, CUBE, Corlytics) do this well and price at levels a 25-person fund manager will never pay.
- **Law firm client alerts** are generic, slow, and don't map to your internal controls.
- **MAS's own email circulars** tell you a document was reissued. They do **not** tell you which of your 200 internal policy paragraphs is now wrong. **That gap is the entire product.**

Our wedge is: Singapore-specific, clause-level, mapped to the customer's own controls, at a price the underserved bottom of the market can pay.

### 2.4 Why this idea and not another

We evaluated five finance-tech businesses. This one won on a single criterion: **the entire data corpus is public, so we can build a fully working, credible demo without a single customer's data.** Reconciliation tools need real payout files. Covenant monitors need real loan agreements. Fee auditors need real transaction data. All blocked on trust we haven't earned yet.

Here, the proof-of-concept **is** the sales asset. We walk into a call with a complete five-year clause-level changelog of Notice 626 and say: "your team reconstructed this by hand; this script did it." That converts an 18-year-old from "kid" into "person who has the thing I need."

### 2.5 Pricing and the number that matters

- SGD 499/month — single licensed entity
- SGD 1,200/month — consultancy licence covering multiple client entities
- Six customers ≈ SGD 3,000 MRR at ~95% gross margin

**We are not solving a scaling problem.** We need roughly six customers. Every architecture decision should optimise for *credibility and correctness*, not throughput.

---

## 3. THE FREE PERIOD — COMMERCIAL MODEL

**The product is free to all users until 31 March 2027. Billing goes live 1 April 2027.**

**Why:** an 18-year-old founder with no track record cannot charge SGD 499/month to a conservative compliance buyer on day one. Free removes the trust barrier, gets real usage data, and buys design partners who will tell us what's actually broken.

**The trap you must help us avoid:** free users are not customers. They reveal nothing about willingness to pay. The standard outcome is fifteen delighted free users and zero conversions.

**How we engineer around it:** users are onboarded as **design partners on a stated future price**, not as free users. Every outreach and every onboarding screen says:

> Free through 31 March 2027. From 1 April, SGD 499/month. Cancel anytime.

This makes free a **discount on a known price**, not a price. It also means we learn in month one whether SGD 499 is credible.

**Implications for you as the engineer:**

- **Do not build billing before February 2027.** It is not on the critical path. (Task T30.)
- **Do build the price into the product early** — onboarding copy, account settings, and email footers state the April price from day one. Trivial to implement, and it's what makes the free period work. (Task T24.)
- **Track engagement from the first design partner onward.** Logins, alerts opened, alerts actioned, control mappings created. In March 2027 the founder needs to know which accounts are genuinely using this and which are dormant, because that determines who converts. Build the events table early — retrofitting analytics loses months of data. (Task T25.)
- **`control_mappings` is the retention moat.** A customer who has mapped 200 internal controls to clauses cannot switch away. Push design partners toward mapping early and make it fast. This is the highest-leverage UX work in the product.

### What changes on 1 April 2027

Billing, company registration, and formal terms. These are founder tasks (§15) with engineering support:

- Business registration with ACRA before invoicing. **Note:** a sole proprietorship trading under the founder's own full name as it appears on his NRIC may be exempt from registration — this must be verified directly with ACRA or a professional, not assumed. Incorporate a Pte Ltd only when a customer's vendor-onboarding process requires a company entity.
- Payment processing (Stripe or HitPay — evaluate at T30, not before).
- Terms of service and a limitation-of-liability clause. Non-negotiable before taking money. See §4.3.
- GST registration is not required until turnover approaches the statutory threshold — verify current threshold with IRAS at the time. At six customers we are nowhere near it.

---

## 4. CONSTRAINTS

### 4.1 Money — hard caps

| Window | Real dates | Cap |
|---|---|---|
| Months 1–6 | Aug 2026 – 31 Jan 2027 | **SGD 0.00.** No paid tiers, no auto-converting trials, no domain purchase. |
| Months 7–12 | 1 Feb 2027 – Jul 2027 | **SGD 100/month total** — DB, hosting, LLM, email, domain combined. |

Because the product is free until April, months 7–9 are funded from the founder's own pocket with zero revenue. **Therefore: defer every paid upgrade until a specific, named pain forces it.** Do not upgrade on schedule. If the free tier still works on 1 February, stay on it. When you do recommend a spend, state exactly what breaks without it.

If any design decision would breach these caps, flag it before writing code and propose the cheaper path.

### 4.2 Infrastructure — locked choices

- **Ingest + diff pipeline:** Python, run on **GitHub Actions cron**. We do not run a server.
- **Read API:** TypeScript + **Hono on Cloudflare Workers**.
  - **Do not use Vercel.** Vercel's Hobby tier prohibits commercial use; the day we invoice on Hobby we're in breach of their ToS. Cloudflare's free tier permits commercial use. This is a legal constraint, not a preference.
- **Database:** Supabase Postgres free tier. Requires `pg_trgm` and `pgcrypto`. Free projects pause after ~7 days idle — our daily cron prevents this; assert it explicitly.
- **Object storage:** Cloudflare R2 for raw PDFs/HTML. **Private bucket, never publicly served.**
- **Email:** Resend free tier.
- **LLM:** Aug 2026–Jan 2027 — Google AI Studio free Gemini tier, or a local model on the founder's laptop for backfill. Feb 2027+ — Gemini Flash paid, USD 8/month ceiling with a hard kill switch (§13).
- **Frontend:** Cloudflare Pages. Plain HTML and minimal JS. **No design system, no component library, no CSS framework beyond one stylesheet** until we have a paying customer. If the demo page needs to look credible — and it does — achieve that with typography and spacing, not dependencies.
- **Domain:** none until Feb 2027. We live on `*.pages.dev`.

**Verify all free-tier limits against live pricing pages before relying on them.** They change.

### 4.3 Legal — these constrain the code, not just the marketing

1. **We do not give legal advice.** Under Singapore's Legal Profession Act, advising on legal obligations is restricted activity. Every output must be **descriptive** — "Clause 6.14 changed; old text: … new text: …; a numeric threshold was modified" — never prescriptive — "you must now do X." **Enforce this in the LLM system prompt AND validate it in code** (§10). Don't leave it to the model's discretion.
2. **We do not mirror the corpus.** MAS documents are Singapore government works. We store raw files privately for diffing and display only the specific changed clauses as short excerpts, always deep-linked to the official MAS URL. **No endpoint may ever return an instrument's full text.** Implement as a hard guard (§11).
3. **We do not touch customer money, portfolios, or trading.** Nothing here goes near MAS-regulated activity. If a feature idea drifts there, kill it and say why.
4. **Crawler etiquette is mandatory.** Respect `robots.txt`. Rate limit ≤1 request per 2 seconds. Descriptive `User-Agent` with a contact email. Use `HEAD`/`ETag`/`Last-Modified` to avoid re-downloading unchanged documents. Getting our IP blocked by MAS ends the company.
5. **Minimise data held.** The corpus is public; the only customer data is email addresses and internal control references. This is deliberate — it means we can answer "we hold no client data" on the vendor security questionnaire every FI will send us. Do not introduce customer data storage without flagging it.

---

## 5. TIMELINE AND GATES

Founder-stated outer bound is 1 April 2027. These intermediate gates are what actually matter.

| Gate | Target | Definition of done | Consequence of missing |
|---|---|---|---|
| **G1 — Diff proof** | ~2 weeks in | `compute_delta` runs on ≥3 real MAS instruments with ≥2 versions each; **false-positive rate under 5%**, manually verified | Everything downstream is worthless. Stop and fix, or change the idea. |
| **G2 — Demo asset** | ~3 weeks | Public static page: complete clause-level changelog for Notice 626 + 2 others, across all obtainable versions | Nothing to send buyers. |
| **G3 — Outreach live** | ~4 weeks | 20 Singapore compliance consultancies contacted with the G2 link. **Founder task — but code must not block it.** | We build blind for seven months. |
| **G4 — First design partner onboarded** | Nov 2026 | One real compliance professional logged in, watchlist configured, ≥5 control mappings created, receiving alerts | We have no feedback loop. |
| **G5 — Price validated** | **31 Jan 2027** | **3 design partners actively using it AND on record accepting SGD 499/month from April** | We reach April with users who never agreed to pay. This is the real deadline. |
| **G6 — Commercial launch** | 1 Apr 2027 | Billing live, entity registered, ToS in place, conversion emails sent | — |

**Work the current gate.** If we're at G1 and the founder asks for billing, say: "that's G6 work; here's what G1 still needs — shall I do that instead?" Offer the alternative, don't just refuse.

---

## 6. THE TASK BACKLOG — YOUR PATH

Execute in order. Each task has a definition of done. Tick them off in the session report. If you think the order is wrong, say so once with reasoning, then follow the founder's call.

### Phase 0 — Reconnaissance (no product code)

- **T1** — Map how MAS publishes instruments today: URL patterns, index pages, RSS/JSON feeds, whether historical versions are retained or overwritten. *DoD: written findings with example URLs.*
- **T2** — Fetch and document `robots.txt`; state exactly what it permits. *DoD: quoted contents + interpretation.*
- **T3** — Sample ≥10 MAS PDFs; determine whether they carry a text layer or are scanned images. *DoD: table of document → text layer yes/no. If >20% are image-only, STOP and flag — that changes the cost model.*
- **T4** — Determine whether issue date and effective date are reliably extractable, and where they appear. *DoD: extraction rule + failure cases.*
- **T5** — Establish whether historical versions are obtainable. Check MAS archives, then fallbacks (Wayback Machine, etc.). *DoD: for 3 named instruments, list of obtainable versions with dates and sources. **This is the highest-risk unknown in the project.***
- **T6** — Catalogue clause numbering conventions and every deviation: annexes, schedules, appendices, tables, footnotes, unnumbered preamble paragraphs. *DoD: spec the parser must satisfy.*
- **T7** — Verify current free-tier limits for Supabase, Cloudflare Workers, R2, Resend, GitHub Actions against live pricing pages. *DoD: table with limits, dates checked, source URLs.*
- **T8** — **Recon report + verdict.** Five-minute read. Ends with a direct answer to: *is clause-level diffing at <5% false positives achievable on real MAS documents?* If no, say no in the first line and propose what to change.

### Phase 1 — Ingest and parse

- **T9** — Repo skeleton per §7; CI on push; `.env.example`; secrets via GitHub/Cloudflare only.
- **T10** — Migration `0001_init.sql` from §8, applied to Supabase.
- **T11** — Source adapter interface + MAS implementation. Rate limiter as a shared enforced primitive, not a `sleep()`.
- **T12** — Fetch → content-hash → dedup → store raw in R2 → write `instrument_versions`. Identical bytes must not create a new version.
- **T13** — PDF → sections parser: strip page furniture, handle multi-level numbering, preserve `ordinal`, normalise whitespace/quotes/non-breaking spaces before hashing. *DoD: 20 real documents, ≥95% clauses correctly segmented, manually spot-checked on 3.*
- **T14** — Backfill historical versions found in T5.

### Phase 2 — The differ (this is the product)

- **T15** — `compute_delta` per §9, three passes.
- **T16** — `trgm_best_match` as a SQL query using the GIN index. Do not load all sections into Python and loop.
- **T17** — Word-level `diff_html` via `difflib.SequenceMatcher` on tokens, wrapped in `<ins>`/`<del>`, **HTML-escaped** (source is an uncontrolled PDF).
- **T18** — `score_severity` per §10.
- **T19** — Golden-file tests + the renumbering test (§12). *DoD: inserting a clause mid-document yields exactly 1 ADDED + N RENUMBERED and **zero** MODIFIED.*
- **T20** — Tune `RENUMBER_THRESHOLD` on real data. *DoD: report measured precision/recall at your chosen value. **G1 gate.***

### Phase 3 — Demo asset

- **T21** — Static changelog generator → Cloudflare Pages. Timeline per instrument: old/new text, dates, severity, MAS source link. Fast, credible, no login. *DoD: **G2 gate.** Founder can send the URL same day.*

### Phase 4 — Tenant layer

- **T22** — Supabase Auth, organisations, memberships, RLS policies + **isolation test proving org A cannot read org B's mappings or alerts** (§8).
- **T23** — Watchlists (by instrument or by entity category) and control mappings CRUD. Optimise mapping entry for speed — bulk paste, autocomplete on clause numbers. This is the moat.
- **T24** — Onboarding flow stating "Free through 31 March 2027, then SGD 499/month, cancel anytime" (§3).
- **T25** — Usage events table + instrumentation: logins, alerts opened, alerts actioned, mappings created. *Do this now; retrofitting loses months of data.*

### Phase 5 — Alerting

- **T26** — Resend integration, two templates: generic watchlist hit, and mapped-control hit ("your control AML-POL-4.2 references Notice 626 §6.14, changed on [date]"). The second is what renews contracts.
- **T27** — Daily cron end-to-end; `crawl_runs` observability; failure alerts to founder. *DoD: **G4 prerequisite** — 14 consecutive days unattended, no manual intervention.*
- **T28** — LLM enrichment gated to severity ≥3, with JSON schema validation and the prescriptive-language filter (§10).

### Phase 6 — Hardening and commercial

- **T29** — Cost guardrails and kill switches (§13); weekly cost report to founder; DB size alarm at 350MB.
- **T30** — *(Feb 2027, not before)* Billing: evaluate Stripe vs HitPay for a Singapore sole proprietor, implement subscriptions, dunning, and a conversion flow for existing design partners.
- **T31** — Schema-drift detection on MAS source formats — alert us before it alerts a customer.
- **T32** — Backups and restore drill. *DoD: an actual restore performed, not just configured.*
- **T33** — Second regulator adapter (ACRA or SGX), proving the source abstraction holds.
- **T34** — Vendor-security-questionnaire pack: data flow diagram, list of subprocessors, "we hold no client data" statement. Founder will be sent one of these by the first serious FI; have it ready.

---

## 7. REPO LAYOUT

```
/AGENTS.md                  # this file
/ingest/                    # Python — crawler, parser, differ
  crawler/                  # per-regulator source adapters
  parse/                    # PDF/HTML → sections
  diff/                     # compute_delta + severity
  enrich/                   # LLM summarisation (gated)
  tests/
    fixtures/               # REAL MAS PDFs, committed, small ones only
/api/                       # TypeScript — Hono on Cloudflare Workers
/web/                       # Cloudflare Pages, minimal
/db/
  migrations/               # numbered, forward-only SQL
/.github/workflows/
  crawl.yml                 # daily cron
  test.yml                  # on push
```

Migrations are **forward-only and numbered**; never edit an applied migration; never let an ORM generate the schema — the SQL in §8 is the source of truth.

No Docker, no Kubernetes, no microservices, no message queue, no Redis. If you believe we need one, make the case first with the specific problem it solves.

Secrets in GitHub Actions / Cloudflare secrets only. `.env.example` committed, `.env` gitignored. If you ever find a key committed, stop and say so immediately.

---

## 8. DATABASE SCHEMA — SOURCE OF TRUTH

Implement as `db/migrations/0001_init.sql`. Extend only via new numbered migrations.

```sql
create extension if not exists pg_trgm;
create extension if not exists pgcrypto;

-- ---------- Corpus (public data) ----------

create table regulators (
  id           smallserial primary key,
  code         text not null unique,          -- 'MAS','ACRA','IRAS','SGX','CEA'
  name         text not null,
  base_url     text not null
);

create table instruments (
  id              bigserial primary key,
  regulator_id    smallint not null references regulators(id),
  external_ref    text not null,              -- 'Notice 626','PSN02','SFA04-N02'
  title           text not null,
  instrument_type text not null,              -- notice|guideline|circular|faq|code|practice_note
  source_url      text not null,
  applies_to      text[] default '{}',        -- ['bank','payment_institution','lfmc']
  is_active       boolean not null default true,
  first_seen_at   timestamptz not null default now(),
  unique (regulator_id, external_ref)
);
create index on instruments using gin (applies_to);

create table instrument_versions (
  id             bigserial primary key,
  instrument_id  bigint not null references instruments(id) on delete cascade,
  content_sha256 char(64) not null,
  r2_key         text not null,
  mime_type      text not null,
  issue_date     date,
  effective_date date,                        -- often differs; drives alert urgency
  fetched_at     timestamptz not null default now(),
  parse_status   text not null default 'pending',   -- pending|parsed|failed
  parse_error    text,
  unique (instrument_id, content_sha256)
);
create index on instrument_versions (instrument_id, fetched_at desc);

create table sections (
  id              bigserial primary key,
  version_id      bigint not null references instrument_versions(id) on delete cascade,
  section_key     text not null,              -- normalised clause number: '6.14.2'
  depth           smallint not null,
  ordinal         integer not null,
  heading         text,
  body            text not null,
  body_sha256     char(64) not null,
  unique (version_id, section_key)
);
create index on sections (version_id, ordinal);
create index sections_body_trgm_idx on sections using gin (body gin_trgm_ops);
```

`sections_body_trgm_idx` is load-bearing — it is how renumbering is solved without embeddings or LLM calls. Do not drop it.

```sql
-- Computed change records. This table IS the product.
create table deltas (
  id                bigserial primary key,
  instrument_id     bigint not null references instruments(id) on delete cascade,
  from_version_id   bigint not null references instrument_versions(id),
  to_version_id     bigint not null references instrument_versions(id),
  op                text not null,            -- ADDED|REMOVED|MODIFIED|RENUMBERED
  old_section_id    bigint references sections(id),
  new_section_id    bigint references sections(id),
  old_section_key   text,
  new_section_key   text,
  similarity        real,
  diff_html         text,
  severity          smallint not null default 3,   -- 1 cosmetic .. 5 new obligation
  ai_summary        text,
  ai_action_hint    text,
  obligation_change boolean not null default false,
  created_at        timestamptz not null default now()
);
create index on deltas (instrument_id, created_at desc);
create index on deltas (to_version_id, severity desc);
create unique index on deltas (from_version_id, to_version_id,
                               coalesce(old_section_id,0), coalesce(new_section_id,0));

-- ---------- Tenant side (RLS enforced) ----------

create table organisations (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  plan        text not null default 'design_partner',
  entity_type text,
  created_at  timestamptz not null default now()
);

create table memberships (
  user_id uuid not null references auth.users(id) on delete cascade,
  org_id  uuid not null references organisations(id) on delete cascade,
  role    text not null default 'member',
  primary key (user_id, org_id)
);

create table watchlists (
  id            bigserial primary key,
  org_id        uuid not null references organisations(id) on delete cascade,
  instrument_id bigint references instruments(id) on delete cascade,
  applies_to    text,
  min_severity  smallint not null default 2,
  check (instrument_id is not null or applies_to is not null),
  unique (org_id, instrument_id, applies_to)
);

-- THE MOAT. 200 mapped controls = switching cost measured in months.
create table control_mappings (
  id              bigserial primary key,
  org_id          uuid not null references organisations(id) on delete cascade,
  instrument_id   bigint not null references instruments(id),
  section_key     text not null,
  internal_ref    text not null,              -- 'AML-POL-4.2','SOP-Onboarding-11'
  owner_email     text,
  notes           text,
  unique (org_id, instrument_id, section_key, internal_ref)
);
create index on control_mappings (instrument_id, section_key);

create table alerts (
  id              bigserial primary key,
  org_id          uuid not null references organisations(id) on delete cascade,
  delta_id        bigint not null references deltas(id) on delete cascade,
  mapping_id      bigint references control_mappings(id) on delete set null,
  status          text not null default 'open',   -- open|acknowledged|actioned|dismissed
  assigned_to     text,
  resolved_at     timestamptz,
  resolution_note text,
  created_at      timestamptz not null default now(),
  unique (org_id, delta_id, mapping_id)
);
create index on alerts (org_id, status, created_at desc);

-- Conversion evidence. Who is actually using this in March 2027?
create table usage_events (
  id         bigserial primary key,
  org_id     uuid references organisations(id) on delete cascade,
  user_id    uuid,
  event_type text not null,      -- login|alert_viewed|alert_actioned|mapping_created|export
  metadata   jsonb default '{}',
  created_at timestamptz not null default now()
);
create index on usage_events (org_id, created_at desc);
create index on usage_events (event_type, created_at desc);

create table crawl_runs (
  id             bigserial primary key,
  regulator_id   smallint not null references regulators(id),
  started_at     timestamptz not null default now(),
  finished_at    timestamptz,
  docs_seen      integer default 0,
  versions_new   integer default 0,
  deltas_created integer default 0,
  status         text not null default 'running',
  error          text
);

alter table organisations    enable row level security;
alter table memberships      enable row level security;
alter table watchlists       enable row level security;
alter table control_mappings enable row level security;
alter table alerts           enable row level security;
alter table usage_events     enable row level security;

create policy org_read on organisations for select
  using (id in (select org_id from memberships where user_id = auth.uid()));

create policy alerts_rw on alerts for all
  using (org_id in (select org_id from memberships where user_id = auth.uid()));
-- Replicate the alerts_rw pattern for watchlists, control_mappings, usage_events.
```

**The RLS isolation test is mandatory (T22).** Authenticate as org A, prove it cannot read org B's `control_mappings` or `alerts`. A leak here ends the company on the first vendor review.

---

## 9. THE DIFF ALGORITHM

Three passes. Pass 2 is where the entire product lives.

```python
CLAUSE_RE = re.compile(r'^\s*(\d+(?:\.\d+)*)[\.\)]?\s+(.*)', re.M)
RENUMBER_THRESHOLD = 0.72   # trigram similarity to call it a move, not add+remove
MODIFY_FLOOR       = 0.35   # below this, treat as unrelated

def normalise(t: str) -> str:
    t = re.sub(r'Page \d+ of \d+', ' ', t)
    t = re.sub(r'\[MAS Notice \d+\s*\]', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()

def compute_delta(db, instrument_id, from_v, to_v):
    old = {s['section_key']: s for s in db.sections(from_v)}
    new = {s['section_key']: s for s in db.sections(to_v)}
    out, matched_new = [], set()

    # PASS 1 — same clause number. Cheap, catches ~90% of real changes.
    for key, o in old.items():
        n = new.get(key)
        if not n:
            continue
        matched_new.add(key)
        if o['body_sha256'] == n['body_sha256']:
            continue                          # UNCHANGED: emit nothing, ever
        out.append(make_delta('MODIFIED', o, n, sim(o['body'], n['body'])))

    # PASS 2 — clause numbers that vanished. Before declaring REMOVED, hunt the
    # new version for the same text under a different number. This is what stops
    # an inserted paragraph 6.14 from producing 200 phantom "changes" and
    # destroying credibility on the first demo call.
    orphan_new = {k: v for k, v in new.items() if k not in matched_new}
    for key, o in old.items():
        if key in matched_new:
            continue
        cand = db.trgm_best_match(         # SELECT ... ORDER BY body <-> $1 LIMIT 1
            body=o['body'], version_id=to_v,
            exclude_keys=list(matched_new)
        )
        if cand and cand['similarity'] >= RENUMBER_THRESHOLD:
            matched_new.add(cand['section_key'])
            op = 'RENUMBERED' if cand['body_sha256'] == o['body_sha256'] else 'MODIFIED'
            out.append(make_delta(op, o, cand, cand['similarity']))
        else:
            out.append(make_delta('REMOVED', o, None, None))

    # PASS 3 — genuinely new clauses.
    for key, n in orphan_new.items():
        if key not in matched_new:
            out.append(make_delta('ADDED', None, n, None))

    return [d for d in out if d['severity'] >= 2]
```

**Requirements:**

- `trgm_best_match` must be SQL against the GIN index (T16).
- `RENUMBER_THRESHOLD = 0.72` is a **starting guess, not a validated constant.** Tune against real documents and report the precision/recall you measured at the value you chose. If you cannot reach <5% false positives at any threshold, the approach is wrong — say so and propose the alternative (candidate options: sentence-level alignment, `pgvector` embeddings on clause bodies, or a two-stage trigram-then-LLM adjudication for the ambiguous band).
- Idempotent. Running twice must not duplicate deltas; the unique index enforces it, handle the conflict cleanly.

---

## 10. SEVERITY AND LLM USAGE

Heuristics first — free and deterministic. LLM only touches severity ≥3.

```python
def score_severity(old_body: str, new_body: str) -> int:
    if old_body and normalise(old_body).lower() == normalise(new_body).lower():
        return 1                                   # casing/whitespace only
    s = 3
    modals = ('shall','must','is required to','may not','shall not','prohibited')
    added_modal = any(m in new_body.lower() and m not in (old_body or '').lower()
                      for m in modals)
    nums_changed = (set(re.findall(r'\b[\d,]+(?:\.\d+)?%?\b', old_body or ''))
                    != set(re.findall(r'\b[\d,]+(?:\.\d+)?%?\b', new_body)))
    dates_changed = bool(re.search(r'\b\d{1,2}\s+\w+\s+20\d\d\b', new_body))
    if nums_changed:  s += 1
    if added_modal:   s += 1
    if dates_changed: s = max(s, 4)
    return min(s, 5)
```

**LLM system prompt — use verbatim:**

```
You compare two versions of a Singapore regulatory clause.
Return ONLY strict JSON, no markdown fences:
{"summary": "<max 30 words, descriptive only>",
 "obligation_change": <bool>,
 "action_hint": "<max 20 words, or empty string>"}
Describe what changed. Do NOT advise on compliance. Do NOT interpret legal effect.
```

**Enforced in code:**

- Validate JSON against a schema. Reject and retry once. On second failure store `null` and set a flag — **never store unparsed model output in `ai_summary`**.
- Reject summaries containing prescriptive phrasing ("you must", "you should", "firms are required to"). Log every rejection so we can see how often the model drifts.
- Log token counts per call. We cannot manage a budget we don't measure.

---

## 11. HARD GUARDS

Code, not policy:

1. **No full-text endpoint.** Cap section bodies per response (≤40% of an instrument's clauses) and per org per day. Write the test that proves the cap holds.
2. **Every delta response carries the official MAS `source_url`.** Non-nullable in the serializer.
3. **R2 bucket private.** No public policy, no signed URLs for raw PDFs handed to end users.
4. **Crawler rate limiter** as a shared enforced primitive.
5. **Prescriptive-language filter** on all AI output.

---

## 12. TESTING

- **Fixture-driven with real MAS PDFs** committed to `ingest/tests/fixtures/`. Synthetic documents will make the differ look like it works when it doesn't.
- **Golden-file tests** on `compute_delta`: known input pair → expected delta set. These catch regressions when thresholds are tuned.
- **Renumbering test:** take a real document, insert a clause mid-way, renumber below, assert exactly 1 ADDED + N RENUMBERED and **zero** MODIFIED.
- **RLS isolation test** (§8).
- CI on push, under 5 minutes.

---

## 13. COST GUARDRAILS

Before the first paid API call, not after the first surprise bill:

- **Monthly LLM token ceiling** in config. On breach: stop LLM calls, keep the deterministic pipeline running, email the founder. Deltas without AI summaries are still a usable product; a blown budget is not.
- **Per-run document cap** so a MAS site restructure exposing 5,000 URLs can't drain us overnight.
- **Weekly cost report** emailed to founder: LLM tokens, Supabase DB size vs limit, R2 storage, Workers requests, Actions minutes.
- **DB size alarm at 350MB.** Full section text grows faster than expected. Mitigation when triggered: keep only recent versions' bodies hot, archive older bodies to R2. Design for it now, implement on trigger.

---

## 14. WHEN TO STOP AND ASK

Halt and flag — with proposed options, not just the problem — if:

- MAS doesn't retain historical versions and backfill isn't reliably achievable.
- More than ~20% of target documents lack a text layer.
- The differ can't reach <5% false positives after genuine tuning.
- Any design would breach the budget cap.
- Any feature approaches regulated activity, legal advice, or republishing the corpus.
- You need a credential, a paid account, or an accepted ToS. **You never create accounts or accept terms on the founder's behalf** — give him the exact steps (§15) and he does it.

Everything else: pick the reasonable interpretation, state the assumption, proceed.

---

## 15. RESPONSE FORMAT — MANDATORY ON EVERY RESPONSE

Every response ends with these two blocks. Not most responses. Every one.

```
## Session Report

**Gate:** G_ | **Tasks completed this session:** T__, T__

**Done (verified):**
- <thing> — verified by <test/command> — output: <result>

**Done (UNVERIFIED):**
- <thing> — could not verify because <reason> — how to verify: <steps>

**Broken / failing:**
- <thing> — <why> — <proposed fix>

**Decisions I made that you should challenge:**
- <assumption or choice> — <alternative if you disagree>

**Cost impact:** <none | +$X/mo | risk of $X>

**Next task:** T__ — <one line>
```

```
## YOUR TURN — WHAT YOU NEED TO DO

**Blocking me (do these first):**
1. <exact action> — <where, e.g. "supabase.com → Project Settings → API"> — <~time>
2. ...

**Not blocking, but do this week:**
1. <action> — <~time>

**Business task (this is the one you'll want to skip):**
- <the sales/outreach/legal action for the current gate>

**Nothing needed from you if this list is empty — say so explicitly.**
```

**Rules for the founder block:**

- **Be specific to the point of tedium.** Not "set up Supabase" — "Go to supabase.com, sign in with GitHub, New Project, name it `mas-delta`, region Singapore, choose a DB password and save it in your password manager, then paste me the Project URL and the `anon` key from Settings → API. Do NOT paste the `service_role` key into chat."
- **Always include a time estimate.** He needs to know if it's 2 minutes or 2 hours.
- **Always include the business task**, even when it's not technical. He is 18 and will hide in the code. Outreach and follow-ups are the actual bottleneck — G3 and G5 are not engineering gates. If the current gate has no business action, say "no business task this week" explicitly, so the omission is deliberate rather than forgotten.
- **Never ask him to hand over a secret you don't need.** Anon keys yes, service-role keys and passwords no — those go in GitHub/Cloudflare secrets, which he sets himself.
- **If he's blocked on nothing, say "Nothing blocking me — here's the business task."** Don't invent busywork.

---

## 16. YOUR FIRST SESSION

Do not write product code.

Execute **T1–T8**. Actually go and look at the MAS website; don't reconstruct it from memory. Verify the free-tier limits against live pricing pages.

Deliver the recon report ending with a direct answer to: **based on what you actually found — not on what this brief assumes — is clause-level diffing achievable at under 5% false positives on real MAS documents?**

If the answer is no, say no in the first line, then tell us what to change.

Then close with §15, both blocks.
