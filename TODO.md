# Founder to-do

Engineering backlog lives in [CLAUDE.md](CLAUDE.md) §6.

Last updated: 25 August 2026

---

## → DO THIS NOW

Do these in order. The token is scoped to a bucket name, so the bucket must exist
under its final name first or the token has to be made twice.

- [ ] **1. Create the bucket `clausewatch-raw`.** R2 → Create bucket → name
      `clausewatch-raw` → location **Asia-Pacific (APAC)** → Create. Leave public access
      **off**. *~2 min*

- [ ] **2. Create the R2 API token.**
      1. `https://dash.cloudflare.com/453137188783dc5aaf71b39099f195ba/r2/api-tokens`
      2. **Create Account API token** (the top button — it survives user changes; the
         User token dies if you leave the org)
      3. Name: `clausewatch-crawler`
      4. Permission: **Object Read & Write**
      5. Scope: **specific bucket** → `clausewatch-raw`
      6. Create. Copy the **Access Key ID** and **Secret Access Key** — shown once.
      7. GitHub repo → Settings → Secrets and variables → **Actions** → New repository
         secret, twice: `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`

      Never paste these into chat. Blocks T12. *~8 min*

- [ ] **3. Delete the old `mas-raw` bucket.** It is empty. *~1 min*

---

## Later — not blocking anything

Parked deliberately. None of this stops the build.

### Naming — standardised on **Clausewatch**

Everything in the repo is renamed: README, package name, crawler user-agent, R2 bucket
config, Terms of Service, build brief title. A Gmail handle being taken does not block
the name — it is not a trademark.

"MAS" is kept **only** where it means the regulator itself: `crawler/mas.py`,
`MasAdapter`, the `MAS` row in `regulators`, the MAS Notice parsing rules, and
`scripts/mas_tracked_oracle.py`. Those are correct — they name the data source, not us.

**Never put "MAS" in the customer-facing name.** Implying affiliation with a statutory
board is a real risk, and ACRA restricts names suggesting a government connection.

Still to rename (founder actions — I cannot do these):
- [ ] **GitHub repo** `mas-delta-engine` → `clausewatch`. Repo → Settings → rename.
      Then tell me and I will update the local remote in one command. GitHub redirects
      the old URL, so nothing breaks immediately.
- [ ] **Supabase project** — name it `clausewatch` when recreating it in Singapore.
- [ ] **Local folder** `~/mas-delta-engine` — optional, cosmetic. Renaming it changes
      your paths; leave it unless it bothers you.

### Official email — and the domain question

The good handles are gone on Gmail, and a Gmail address is weak for this buyer anyway.
A domain solves the email, the demo URL, and deliverability in one purchase.

**The budget rule says no domain before Feb 2027. I think this is the exception, and
here is the case — your call.**

What breaks without a domain, specifically:
- Outreach to conservative compliance firms comes from `something@gmail.com`. These are
  people whose job is detecting things that look wrong.
- Cold email from a free Gmail lands in spam far more often than from a domain with
  proper SPF/DKIM.
- The demo link is `*.pages.dev`, which reads as a hobby project to a buyer deciding
  whether to trust you with a compliance dependency.

Cost: roughly **SGD 15–25/year** for a `.com`. Against a SGD 499/month product, one
extra reply pays for it many times over.

Recommendation: buy it **before G3 outreach**, not before. It is not needed to build the
demo, so it does not block anything today.

- [ ] Decide: domain now, or Gmail for the first outreach round
- [ ] If domain: buy it (Cloudflare Registrar sells at cost), then set up email
- [ ] Either way the address must be **monitored** — PDPA gives people a right to reach
      the DPO and get a reply within 30 days
- [ ] Not the school address; it gets revoked and it reads badly to this buyer

### Supabase region (Tokyo → Singapore)
Currently `ap-northeast-1` (Tokyo). Works fine. The only cost of staying is a longer
answer to "where is our data hosted?" on vendor questionnaires. Free to move while there
is no data; a real migration later.

- [ ] New Project, same `mas` org, region **Southeast Asia (Singapore)**
- [ ] SQL Editor → run `db/migrations/0001_init.sql`, then `0002_lock_corpus_rls.sql`, in
      that order
- [ ] Send the new **Project URL** + **publishable key** (not the secret key)
- [ ] Delete the Tokyo project **only after** the new one is confirmed working
- [ ] All keys rotate as a side effect — no separate rotation needed

### DPO
- [ ] Appoint one (realistically you) and fill `[DPO NAME]` / `[DPO EMAIL]` in
      [docs/legal/privacy-policy.md](docs/legal/privacy-policy.md). Required by PDPA
      s.11, no small-business exemption, contact must be public.

### Sales
- [ ] Finish the 20-firm list —
      [outreach/consultancy-prospects.xlsx](outreach/consultancy-prospects.xlsx).
      Green Tier A rows first. Confirm or drop the unverified "Ardent Associates" row.
- [ ] Send the 20 emails once the demo page is live — this is gate G3.
- [ ] Follow up. The third email is the one that works.

### Before taking money (1 April 2027)
- [ ] ACRA registration, or confirm sole-proprietor exemption **with ACRA directly**
- [ ] Lawyer review of the [ToS](docs/legal/terms-of-service.md) and
      [privacy policy](docs/legal/privacy-policy.md) — both unreviewed drafts
- [ ] Fill every `[PLACEHOLDER]` in both
- [ ] Record terms acceptance at signup (date, version, user) — **not built**
- [ ] Payment processing: Stripe vs HitPay (T30, Feb 2027, not before)
- [ ] Verify the GST threshold with IRAS at the time

---

## Key hygiene — checked 25 Aug 2026, no action needed

No secret is committed. Only the Supabase Project URL and publishable key are in
`.env.example`, both public by design; `SUPABASE_SECRET_KEY` there is a placeholder.
`.env` is gitignored and absent. No DB password, connection string, or private key in
the repo or its history.

The publishable key is safe **because** RLS is enabled (migration 0002). If RLS is ever
disabled on a corpus table, that key becomes dangerous again.

Rotate immediately if a secret key or DB password is ever pasted into chat, a
screenshot, a commit, or a support ticket.

## Done

- [x] Supabase project created (Tokyo), migrations `0001` and `0002` applied and verified
- [x] Corpus locked down — public key can no longer read or write it
- [x] GitHub repo, CI green on every commit
- [x] Cloudflare R2 bucket created, Asia-Pacific, private (rename to `clausewatch-raw` pending)
