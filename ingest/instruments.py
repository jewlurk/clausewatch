"""Instruments we track.

Scope is deliberately Singapore AML/CFT across every institution type MAS regulates.
That makes one coherent story for a buyer — "we cover your AML/CFT obligations,
whichever licence you hold" — and it matches the target segments directly: banks
(626), payment institutions (PSN01), digital payment token services (PSN02), and
capital markets intermediaries including fund managers (SFA04-N02).

Landing URLs verified live 2026-08-25. They are not guessable: SFA04-N02 sits at
`notice-sfa-04-n02` with hyphens the other notices do not use, so every URL here was
confirmed by fetching it.

`applies_to` feeds watchlists by entity category (schema §8), so a customer can follow
"everything that applies to a major payment institution" instead of naming instruments.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class InstrumentSpec:
    external_ref: str
    title: str
    landing_url: str
    instrument_type: str = "notice"
    applies_to: tuple[str, ...] = field(default_factory=tuple)


MAS_INSTRUMENTS: tuple[InstrumentSpec, ...] = (
    InstrumentSpec(
        external_ref="Notice 626",
        title=(
            "Prevention of Money Laundering and Countering the Financing of "
            "Terrorism - Banks"
        ),
        landing_url="https://www.mas.gov.sg/regulation/notices/notice-626",
        applies_to=("bank",),
    ),
    InstrumentSpec(
        external_ref="Notice 626A",
        title=(
            "Prevention of Money Laundering and Countering the Financing of "
            "Terrorism - Merchant Banks"
        ),
        landing_url="https://www.mas.gov.sg/regulation/notices/notice-626a",
        applies_to=("merchant_bank",),
    ),
    InstrumentSpec(
        external_ref="PSN01",
        title=(
            "Prevention of Money Laundering and Countering the Financing of "
            "Terrorism - Specified Payment Services"
        ),
        landing_url=(
            "https://www.mas.gov.sg/regulation/notices/"
            "psn01-aml-cft-notice---specified-payment-services"
        ),
        applies_to=("payment_institution",),
    ),
    InstrumentSpec(
        external_ref="PSN02",
        title=(
            "Prevention of Money Laundering and Countering the Financing of "
            "Terrorism - Digital Payment Token Service"
        ),
        landing_url=(
            "https://www.mas.gov.sg/regulation/notices/"
            "psn02-aml-cft-notice---digital-payment-token-service"
        ),
        applies_to=("digital_payment_token_service",),
    ),
    InstrumentSpec(
        external_ref="SFA04-N02",
        title=(
            "Prevention of Money Laundering and Countering the Financing of "
            "Terrorism - Capital Markets Intermediaries"
        ),
        landing_url="https://www.mas.gov.sg/regulation/notices/notice-sfa-04-n02",
        applies_to=("lfmc", "rfmc", "capital_markets_intermediary"),
    ),
)


def by_ref(external_ref: str) -> InstrumentSpec:
    for spec in MAS_INSTRUMENTS:
        if spec.external_ref == external_ref:
            return spec
    raise KeyError(external_ref)
