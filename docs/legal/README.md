# Legal documents — DRAFTS

**Status: unreviewed drafts. Not legal advice. I am not a lawyer.**

These cover the risks that are specific to this product rather than generic SaaS
boilerplate, so a lawyer is reviewing something concrete instead of drafting from
scratch — that is the cost saving. They are **not** a substitute for review by a
Singapore-qualified lawyer before you take a single dollar.

## What's here

- `terms-of-service.md` — the contract, incl. the completeness disclaimer (§4 below).
- `privacy-policy.md` — PDPA privacy notice, incl. subprocessors and DPO.
- `vendor-security.md` — **the vendor security & data-handling pack (T34).** The first
  serious FI will send its own security questionnaire; this is the answer to send back.
  It is a factual technical description of the system as built — data held, data flow,
  subprocessors, tenant isolation, controls — and it states the maturity gaps (no SOC 2,
  no pentest) plainly rather than hiding them. Same `[PLACEHOLDER]` discipline: fill
  entity name, DPO, and date before sending. Its claims are testable against the code,
  so keep it in sync when the architecture changes.

## What must be filled in before these go live

Every placeholder is in `[SQUARE BRACKETS]`. You cannot publish with them unfilled:

| Placeholder | Where it comes from |
|---|---|
| `[LEGAL ENTITY NAME]` | Your ACRA registration, or your full name as on your NRIC if trading as an exempt sole proprietor |
| `[UEN]` | ACRA, once registered. Omit the line entirely if not yet registered |
| `[BUSINESS ADDRESS]` | Required for PDPA contactability |
| `[DPO NAME]` | Legally required — see below |
| `[CONTACT EMAIL]` / `[DPO EMAIL]` | A monitored address. Not a personal address you ignore |
| `[EFFECTIVE DATE]` | The date you publish them |

## Two hard legal points these documents turn on

**1. Data Protection Officer is mandatory.** Under PDPA s.11 every organisation that
handles personal data must appoint a DPO and **make their business contact details
publicly available** — there is no small-business exemption. A one-person business with
five email addresses has the same obligation as a bank. The DPO can be you, and needs no
formal qualification. Put the contact in the privacy policy and keep it monitored.

**2. Do not drift into legal advice.** Legal Profession Act 1966 s.33 makes unauthorised
practice of law a criminal offence, not merely a civil risk. This is why the product is
built to be *descriptive* ("clause 6.14 changed; old text X, new text Y") and never
*prescriptive* ("you must now do Z"), why the LLM prompt forbids interpretation, and why
there is a code-level filter on prescriptive phrasing. **The engineering guard and the
contractual disclaimer have to stay aligned.** If a future feature starts telling
customers what to do, the disclaimer stops protecting you.

## The clause you will be tempted to soften

`docs/legal/terms-of-service.md` §4 discloses that the service **can miss changes**, and
names the current known gaps: footnote-only amendments, and changes invisible to text
extraction (measured — see [threshold-tuning.md](../threshold-tuning.md), para 6.24).

Leave it in. Two reasons:

- Legally, a disclaimer of completeness is far stronger when you can show you disclosed
  specific known limitations rather than hiding behind generic "as is" language.
- Commercially, compliance buyers are professional sceptics. "Here is exactly what we
  catch and what we do not, measured against MAS's own document" is more credible than
  a claim of perfection they will not believe anyway.

## Before taking money (1 April 2027)

- [ ] Lawyer review of both documents
- [ ] Business registered with ACRA, or exemption confirmed **with ACRA directly** — do not assume
- [ ] DPO appointed and contact published
- [ ] Entity name and address filled into both documents
- [ ] Documents published at stable URLs and linked from the site footer and onboarding
- [ ] Terms acceptance recorded at signup (date, version, user) — currently not implemented
- [ ] `vendor-security.md` placeholders filled — but this one is needed for the **first
      serious sales conversation**, not just before revenue: an FI sends the
      questionnaire during evaluation, well before you invoice

## Where these should live

Drafts here. Once reviewed, they become pages under `web/legal/` and get stable URLs.
Version them: keep old versions accessible, since customers agreed to a specific text.
