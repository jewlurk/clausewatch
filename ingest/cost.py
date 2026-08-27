"""Cost model and health thresholds (T29, brief §13).

Pure functions — no network, no database — so the arithmetic that decides whether to
raise an alarm is testable without standing up any infrastructure. scripts/cost_report.py
gathers the live numbers and feeds them here.

Prices verified against the claude-api model table on 26 August 2026:
claude-haiku-4-5 is USD 1.00 per million input tokens, USD 5.00 per million output.
The pipeline uses Haiku for summaries (enrich/summarise.py) and nothing else, so this is
the only model priced here. Add a row before pointing the summariser at another model.
"""
from __future__ import annotations

from dataclasses import dataclass

# USD per million tokens. The source of truth is the provider's pricing page; this is a
# cache with the date it was checked, exactly as the free-tier limits are treated.
MODEL_PRICES: dict[str, tuple[float, float]] = {
    # model: (input $/1M, output $/1M) — checked 2026-08-26
    "claude-haiku-4-5": (1.00, 5.00),
}

# Supabase free tier is 500 MB. Alarm well before the ceiling so there is time to act —
# §13 names 350 MB. Mitigation when it trips: archive older versions' section bodies to
# R2 and keep only recent ones hot (designed for in §13, implemented on trigger).
DB_LIMIT_MB = 500
DB_ALARM_MB = 350

# R2 free tier is 10 GB. The corpus is a few dozen MB, so this is a distant tripwire,
# not a live constraint — but a MAS site restructure that exposed thousands of URLs
# could fill it, and §13 wants that visible before the bill, not after.
R2_LIMIT_GB = 10
R2_ALARM_GB = 7


def llm_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """USD for a token count, or None when the model is not priced here.

    None rather than 0.0 on an unknown model: a silent zero would read as "free" on the
    cost report, which is the one reading that must never be wrong on a budget page.
    """
    price = MODEL_PRICES.get(model)
    if price is None:
        return None
    input_rate, output_rate = price
    return input_tokens / 1_000_000 * input_rate + output_tokens / 1_000_000 * output_rate


@dataclass(frozen=True)
class Threshold:
    """A measured value against its alarm and hard limit."""

    label: str
    value: float
    unit: str
    alarm: float
    limit: float

    @property
    def breached(self) -> bool:
        return self.value >= self.alarm

    @property
    def pct_of_limit(self) -> float:
        return self.value / self.limit * 100 if self.limit else 0.0

    def line(self) -> str:
        mark = "  ALARM" if self.breached else ""
        return (
            f"{self.label}: {self.value:.1f} {self.unit} "
            f"({self.pct_of_limit:.0f}% of {self.limit:g} {self.unit} limit, "
            f"alarm at {self.alarm:g}){mark}"
        )


def db_threshold(size_mb: float) -> Threshold:
    return Threshold("Database", size_mb, "MB", DB_ALARM_MB, DB_LIMIT_MB)


def r2_threshold(size_bytes: int) -> Threshold:
    gb = size_bytes / 1_000_000_000
    return Threshold("R2 storage", gb, "GB", R2_ALARM_GB, R2_LIMIT_GB)
