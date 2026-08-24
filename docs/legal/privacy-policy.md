# Privacy Policy

**DRAFT — not reviewed by a lawyer. Do not publish until reviewed and placeholders filled.**

**Effective date:** [EFFECTIVE DATE]
**Version:** 1.0

This Policy explains how [LEGAL ENTITY NAME] (UEN [UEN]) ("**we**", "**us**") collects,
uses, discloses and protects personal data in connection with the MAS Regulatory Delta
Engine (the "**Service**"), in accordance with the Personal Data Protection Act 2012 of
Singapore (the "**PDPA**").

---

## 1. Our approach: we hold as little as possible

The regulatory corpus we process is **public data published by MAS**. It contains no
personal data of yours or of your clients.

The only personal data we hold is what is needed to give you an account and send you
alerts. We do not want, request, or require your internal policies, your customers'
records, transaction data, or any personal data belonging to your clients.

This is deliberate. It means that when a financial institution sends you a vendor
security questionnaire, the honest answer to "what client data does this vendor hold?" is
**none**.

## 2. Data Protection Officer

As required by section 11 of the PDPA we have appointed a Data Protection Officer.

**Data Protection Officer:** [DPO NAME]
**Email:** [DPO EMAIL]
**Address:** [BUSINESS ADDRESS]

Direct any question, access or correction request, withdrawal of consent, or complaint
about personal data to the DPO. We aim to respond within **30 days**; if we cannot, we
will tell you when to expect a response.

## 3. Personal data we collect

| Category | Examples | Source |
|---|---|---|
| Account data | Name, work email address, organisation name, role | You, at registration |
| Authentication data | Hashed credentials, session tokens, login timestamps | Generated when you sign in |
| Configuration data | Watchlists, internal control references (e.g. "AML-POL-4.2"), owner email addresses you assign, notes | You, when configuring |
| Usage data | Logins, alerts viewed, alerts actioned, mappings created, exports | Generated as you use the Service |
| Communications | Emails you send us and our replies | You |
| Technical data | IP address, browser type, timestamps, error logs | Automatically, when you use the Service |

**We do not collect** NRIC or other government identification numbers, payment card
details (any future payment processor collects those directly), special categories of
sensitive personal data, or your clients' personal data.

Internal control references are intended to be organisational identifiers, not personal
data. Where you choose to enter a person's name or email — for example as a control owner
— that becomes personal data you are responsible for having a basis to provide.

## 4. Why we use it

We use personal data only for these purposes:

  (a) to create and administer your account and authenticate you;

  (b) to provide the Service, including matching regulatory changes to your watchlists
  and control mappings;

  (c) to send you alerts and service communications you have configured or requested;

  (d) to provide support and respond to your enquiries;

  (e) to maintain the security, integrity and availability of the Service, and to detect
  and prevent abuse;

  (f) to understand which features are used, so we can improve the Service and decide
  what to build;

  (g) to invoice you and administer your subscription, once the Service becomes
  chargeable; and

  (h) to comply with legal obligations.

We do **not** sell personal data. We do **not** use it for third-party advertising or
profiling.

## 5. Consent and its withdrawal

We collect, use and disclose personal data with your consent, or where the PDPA otherwise
permits it — including where it is necessary to perform our contract with you, or for
legitimate interests such as securing the Service.

You may withdraw consent at any time by writing to the DPO. We will tell you the likely
consequences: withdrawing consent for the data needed to operate your account means we
can no longer provide the Service, and the account will be closed. Withdrawal does not
affect processing already carried out, or retention we are legally required to maintain.

## 6. Disclosure and service providers

We do not disclose personal data except:

  (a) to the service providers listed below, who process it on our behalf under
  contractual obligations to protect it and use it only on our instructions;

  (b) where required by law, court order, or a regulator with jurisdiction;

  (c) to protect our rights, safety, or property, or those of others; or

  (d) to a successor entity in a merger, acquisition, or sale of assets, on notice to you.

### Service providers (subprocessors)

| Provider | Purpose | Data | Location |
|---|---|---|---|
| Supabase | Database and authentication | Account, configuration, usage data | [PENDING — currently Tokyo (ap-northeast-1); move to Singapore planned] |
| Cloudflare | Application hosting, object storage, network security | Technical data; raw MAS documents (no personal data) | Global edge network |
| Resend | Sending alert and service emails | Name, email address, message content | United States |
| GitHub | Runs the scheduled processing pipeline | No customer personal data | United States |
| Google (Gemini API) | Generating descriptive summaries of regulatory changes | **Public MAS text only. No customer personal data is ever sent.** | United States |

We keep this list current. Material changes will be notified.

## 7. Transfers outside Singapore

Some providers process data outside Singapore, as shown above. Where personal data is
transferred out of Singapore we take reasonable steps to ensure the recipient is bound to
a standard of protection comparable to the PDPA, in accordance with section 26 of the
PDPA and the Personal Data Protection Regulations, ordinarily through contractual terms
including the provider's data processing agreement.

## 8. Retention

We keep personal data only as long as needed for the purposes above or as required by
law.

| Data | Retention |
|---|---|
| Account and configuration data | While your account is active |
| After account closure | Deleted or anonymised within **90 days**, unless retention is legally required |
| Usage data | Up to **24 months**, then aggregated or deleted |
| Technical logs | Up to **12 months** |
| Billing records | As required by Singapore tax and accounting law (currently at least **5 years**) |
| Correspondence | Up to **24 months** after the matter closes |

The regulatory corpus itself is public data and is retained indefinitely — that history
is the product.

## 9. Security

We apply reasonable security arrangements, including: encryption in transit (HTTPS);
encryption at rest by our infrastructure providers; database row-level security so one
organisation's data is not readable by another; storing raw documents in a private,
non-public bucket; restricting administrative access to those who need it; keeping
credentials in dedicated secret stores, never in source code; and applying the principle
of least privilege to keys.

No system is perfectly secure and we cannot guarantee absolute security. Keep your
credentials confidential and tell us immediately of any suspected compromise.

## 10. Data breaches

If a data breach occurs that results in, or is likely to result in, significant harm to
affected individuals, or is of a significant scale, we will notify the Personal Data
Protection Commission and affected individuals as required by Part 6A of the PDPA, within
the timeframes the PDPA prescribes.

## 11. Your rights

Under the PDPA you may:

  (a) **access** the personal data we hold about you and information about how it has
  been used or disclosed in the past year;

  (b) **correct** inaccurate or incomplete personal data;

  (c) **withdraw consent** to our collection, use or disclosure; and

  (d) **complain** to us and, if unsatisfied, to the Personal Data Protection Commission
  of Singapore.

Contact the DPO at [DPO EMAIL]. We may need to verify your identity, and may charge a
reasonable fee for an access request as permitted by the PDPA.

Much of your data can also be viewed and corrected directly in your account settings.

## 12. Cookies and similar technologies

We use only cookies that are strictly necessary to operate the Service — keeping you
signed in and maintaining your session securely. We do not use advertising cookies or
third-party tracking cookies.

Blocking strictly necessary cookies will prevent you from signing in.

## 13. Children

The Service is a business tool and is not directed at anyone under 18. We do not
knowingly collect personal data from children. If you believe we have, contact the DPO
and we will delete it.

## 14. Changes to this Policy

We may update this Policy. We will publish the updated version with a new effective date
and, where changes materially affect your rights, give reasonable advance notice. The
current version is always available on our website.

## 15. Contact

**Data Protection Officer:** [DPO NAME]
Email: [DPO EMAIL]

[LEGAL ENTITY NAME]
[BUSINESS ADDRESS]

If you are not satisfied with our response you may contact the Personal Data Protection
Commission of Singapore at [pdpc.gov.sg](https://www.pdpc.gov.sg).
