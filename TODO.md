# Founder to-do

Tasks only the founder can do — accounts, credentials, decisions, and sales.
Engineering backlog lives in [CLAUDE.md](CLAUDE.md) §6.

Last updated: 25 August 2026

---

## Blocking engineering right now

- [ ] **R2 API token** → put into GitHub Actions secrets as `R2_ACCESS_KEY_ID` and
      `R2_SECRET_ACCESS_KEY`. Never paste them into chat. Blocks T12 (storing raw PDFs).
      *~10 min*
- [ ] **Recreate the Supabase project in Singapore.** Currently Tokyo
      (`ap-northeast-1`), confirmed in the dashboard. The region cannot be changed in
      place. Free to do now (no data, no users); a real migration once design partners
      exist. Until it is done the privacy policy cannot state a hosting location.
      *~15 min*

      Do this **after** settling the name, so the project is named right first time.

      1. supabase.com → **New Project**, same `mas` org. The free tier allows two
         projects, so keep the Tokyo one until the new one is verified.
      2. Name: `clausewatch` (or whatever the confirmed name is).
      3. Region: **Southeast Asia (Singapore)** — `ap-southeast-1`.
      4. New DB password → password manager. Never paste it into chat.
      5. SQL Editor → run `db/migrations/0001_init.sql`, then
         `db/migrations/0002_lock_corpus_rls.sql`. **In that order.**
      6. Settings → API Keys → send the new **Project URL** and **publishable key**
         (not the secret key).
      7. Wait for confirmation the new project works.
      8. Only then delete the Tokyo project.

      All keys rotate as a side effect, so no separate key rotation is needed.

## Decisions pending

- [ ] **Confirm the name.** Working name: **Clausewatch** (provisional, not confirmed).
      Before committing, check: ACRA name availability via BizFile, `.com`/`.sg` domain
      availability, and that no financial-compliance business already uses it.
      Needed for the demo page and outreach emails, not for anything legal yet.
      *~15 min*
- [ ] **Create the official email address**, once the name is settled. A dedicated free
      Gmail for now; becomes `dpo@<domain>` when the domain is bought (Feb 2027).
      Used for: DPO contact, crawler user-agent, outreach replies.
      **Not** the school address — it will be revoked, and it undercuts credibility with
      compliance buyers. Must be monitored: PDPA gives people the right to contact the
      DPO and expect a reply within 30 days. *~5 min*
- [ ] **Appoint the DPO** (realistically you). Legally required under PDPA s.11 with no
      small-business exemption, and the contact must be publicly published. Fill
      `[DPO NAME]` and `[DPO EMAIL]` in
      [docs/legal/privacy-policy.md](docs/legal/privacy-policy.md). *~5 min*

### Renaming, once the name is confirmed

Rename only what customers actually see. Everything else is internal and changing it
is busywork.

- [ ] Demo page URL — the `*.pages.dev` project name. It is the link in every outreach
      email, so get it right before sending any.
- [ ] Email address (see above).
- [ ] Branding on the demo page itself.
- [ ] *Optional:* the GitHub repo name. Only visible if you show someone the repo.
      Renaming changes the remote URL, so it needs a one-line `git remote set-url`.
- [ ] *Skip:* R2 bucket `mas-raw` and the Supabase project name. Customers never see
      either. R2 buckets cannot be renamed, so changing it means recreating a bucket for
      no benefit.

**Never use "MAS" in the customer-facing name.** MAS is a statutory board; implying
affiliation or endorsement is a real risk, and ACRA restricts names suggesting a
government connection. The repo codename is fine; the brand is not.

## Sales — the real bottleneck

- [ ] **Finish the 20-firm prospect list** —
      [outreach/consultancy-prospects.xlsx](outreach/consultancy-prospects.xlsx).
      Fill the email and contact-person columns for the green Tier A rows first; those
      are the bullseye (boutique firms, 3–20 people). Verify each email on the firm's
      own site; find a named compliance director/partner on LinkedIn. Also confirm or
      drop the "Ardent Associates" row — its domain is unverified. *~1 day*
- [ ] **Send the 20 outreach emails** once the demo page (G2) is live. This is gate G3.
      Nothing downstream happens without it.
- [ ] **Follow up.** The first email is not the outreach; the third one is.

## Before taking money (1 April 2027) — not now

- [ ] Register with ACRA, or confirm sole-proprietor exemption **with ACRA directly**
      rather than assuming
- [ ] Lawyer review of [terms of service](docs/legal/terms-of-service.md) and
      [privacy policy](docs/legal/privacy-policy.md) — both are unreviewed drafts
- [ ] Fill every `[PLACEHOLDER]` in both documents
- [ ] Publish both at stable URLs, linked from the footer and onboarding
- [ ] Record terms acceptance at signup (date, version, user) — **not built yet**;
      you must be able to prove what a customer agreed to
- [ ] Payment processing — evaluate Stripe vs HitPay (T30, Feb 2027, not before)
- [ ] Verify GST threshold with IRAS at the time (nowhere near it at six customers)

## Key hygiene — checked 25 Aug 2026, no action needed

Scanned the repo and its history: no secret is committed. Only the Supabase **Project
URL** and **publishable key** are in `.env.example`, and both are public by design.
`SUPABASE_SECRET_KEY` there is a placeholder. `.env` is gitignored and absent. No DB
password, connection string, or private key anywhere.

The publishable key being public is only safe **because** RLS is enabled (migration
0002). Before that it could delete the corpus. If RLS is ever disabled on a corpus
table, that key becomes dangerous again.

Rotate immediately — Supabase → Settings → API Keys — if a secret key or DB password is
ever pasted into chat, a screenshot, a commit, or a support ticket.

## Done

- [x] Supabase project created (region Tokyo — move to Singapore pending, see above)
- [x] Migration `0001_init.sql` applied — verified, all 9 tables live
- [x] Migration `0002_lock_corpus_rls.sql` applied — verified, corpus no longer
      readable or writable with the public key
- [x] GitHub repo created, `harman-0` added as collaborator, CI green
- [x] Cloudflare R2 bucket `mas-raw` created, Asia-Pacific, private
