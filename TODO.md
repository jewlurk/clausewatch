# Founder to-do

Tasks only the founder can do — accounts, credentials, decisions, and sales.
Engineering backlog lives in [CLAUDE.md](CLAUDE.md) §6.

Last updated: 25 August 2026

---

## Blocking engineering right now

- [ ] **R2 API token** → put into GitHub Actions secrets as `R2_ACCESS_KEY_ID` and
      `R2_SECRET_ACCESS_KEY`. Never paste them into chat. Blocks T12 (storing raw PDFs).
      *~10 min*
- [ ] **Move Supabase to Singapore.** Currently Tokyo (`ap-northeast-1`) — confirmed in
      the dashboard. Region cannot be changed in place, so it means a new project; free
      while there is no data. Steps in the session notes. Until this is done the privacy
      policy cannot state a hosting location. *~15 min*

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

## Done

- [x] Supabase project created (region Tokyo — move to Singapore pending, see above)
- [x] Migration `0001_init.sql` applied — verified, all 9 tables live
- [x] Migration `0002_lock_corpus_rls.sql` applied — verified, corpus no longer
      readable or writable with the public key
- [x] GitHub repo created, `harman-0` added as collaborator, CI green
- [x] Cloudflare R2 bucket `mas-raw` created, Asia-Pacific, private
