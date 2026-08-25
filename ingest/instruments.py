"""Instruments we track.

Scope: every **active** MAS AML/CFT notice — one per licensed entity type. That makes a
single coherent promise to a buyer ("your AML/CFT obligations, whichever licence you
hold") and covers essentially every MAS-regulated firm, without drifting into unrelated
regulation whose documents are structured differently and whose accuracy we have not
measured.

Two notices are deliberately absent. Notice 3001 (money-changers and remittance) and
PSOA-N02 (stored value facilities) are marked **[Cancelled]** by MAS — superseded by
the Payment Services Act regime now covered by PSN01 and PSN02. Letting a customer
follow a dead notice would be worse than not covering it.

Every landing URL and title here was read from the live MAS page, not constructed.
That caught two errors worth noting: Notice 626A binds **credit and charge card
licensees**, not merchant banks (that is Notice 1014), and SFA13-N01 sits at
`notice-sfa-13-n01` with hyphens the other notices do not use.

`applies_to` drives watchlists by entity category, so a firm can follow "everything
that applies to a licensed trust company" rather than naming instruments.
"""
from __future__ import annotations

from dataclasses import dataclass, field

BASE = "https://www.mas.gov.sg/regulation/notices/"
AML = "Prevention of Money Laundering and Countering the Financing of Terrorism"


@dataclass(frozen=True)
class InstrumentSpec:
    external_ref: str
    title: str
    landing_url: str
    audience: str  # plain-English "who this binds", shown in the console
    instrument_type: str = "notice"
    applies_to: tuple[str, ...] = field(default_factory=tuple)


def _spec(ref: str, slug: str, audience: str, *applies: str) -> InstrumentSpec:
    return InstrumentSpec(
        external_ref=ref,
        title=f"{AML} - {audience}",
        landing_url=BASE + slug,
        audience=audience,
        applies_to=applies,
    )


MAS_INSTRUMENTS: tuple[InstrumentSpec, ...] = (
    _spec("Notice 626", "notice-626", "Banks", "bank"),
    _spec("Notice 626A", "notice-626a",
          "Credit Card or Charge Card Licensees", "card_licensee"),
    _spec("Notice 1014", "notice-1014", "Merchant Banks", "merchant_bank"),
    _spec("Notice 824", "notice-824", "Finance Companies", "finance_company"),
    _spec("Notice 314", "notice-314", "Life Insurers", "life_insurer"),
    _spec("SFA04-N02", "notice-sfa-04-n02",
          "Capital Markets Intermediaries",
          "capital_markets_intermediary", "lfmc", "rfmc"),
    _spec("SFA13-N01", "notice-sfa-13-n01", "Approved Trustees", "approved_trustee"),
    _spec("FAA-N06", "notice-faa-n06", "Financial Advisers", "financial_adviser"),
    _spec("TCA-N03", "notice-tca-n03", "Trust Companies", "trust_company"),
    _spec("PSN01", "psn01-aml-cft-notice---specified-payment-services",
          "Specified Payment Services", "payment_institution"),
    _spec("PSN02", "psn02-aml-cft-notice---digital-payment-token-service",
          "Digital Payment Token Services", "digital_payment_token_service"),
)


def by_ref(external_ref: str) -> InstrumentSpec:
    for spec in MAS_INSTRUMENTS:
        if spec.external_ref == external_ref:
            return spec
    raise KeyError(external_ref)
