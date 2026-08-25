"""Plain-language summaries of clause changes (T28).

Why this exists: a diff shows a compliance officer *what* moved, but reading 300
word-level diffs to find the three that matter is work. A one-line summary per change
makes the feed scannable.

Three constraints shape every line of this module:

* **Legal.** Legal Profession Act 1966 s.33 makes advising on legal obligations a
  criminal offence for the unqualified. The system prompt forbids interpretation, and
  a filter re-checks the output — the model's compliance is not assumed. A rejected
  summary is dropped, never stored.
* **Budget.** §13 requires a token ceiling with a kill switch. When the ceiling is
  hit, enrichment stops and the deterministic pipeline continues; deltas without
  summaries are still a usable product, a surprise bill is not.
* **Trust.** Only public MAS text is ever sent. No customer data reaches the API —
  that is a promise made in the privacy policy and on the vendor questionnaire.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

# Verbatim from the brief §10. Descriptive only — this is the legal boundary.
SYSTEM_PROMPT = """You compare two versions of a Singapore regulatory clause.
Return ONLY strict JSON, no markdown fences:
{"summary": "<max 30 words, descriptive only>",
 "obligation_change": <bool>,
 "action_hint": "<max 20 words, or empty string>"}
Describe what changed. Do NOT advise on compliance. Do NOT interpret legal effect."""

# Phrasing that turns description into advice. Checked against the model's output
# because a prompt is a request, not a guarantee.
PRESCRIPTIVE = (
    "you must", "you should", "you need to", "you are required",
    "firms must", "firms should", "firms are required",
    "banks must", "banks should", "we recommend", "you will need",
    "ensure that you", "make sure you", "it is advisable", "should now",
)

MODEL = os.environ.get("LLM_MODEL", "claude-opus-5")
MIN_SEVERITY = 3  # §10: the LLM only ever sees severity >= 3


class ChangeSummary(BaseModel):
    """Schema the model must satisfy. Validation is the SDK's job, not a regex."""

    summary: str = Field(description="Max 30 words, descriptive only")
    obligation_change: bool = Field(description="Whether an obligation changed")
    action_hint: str = Field(default="", description="Max 20 words, or empty")


@dataclass
class EnrichmentBudget:
    """§13 kill switch. Counts tokens actually billed, not tokens estimated."""

    ceiling: int = int(os.environ.get("LLM_MONTHLY_TOKEN_CEILING", "2000000"))
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    rejected: list[str] = field(default_factory=list)

    @property
    def used(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def exhausted(self) -> bool:
        return self.used >= self.ceiling

    def record(self, usage) -> None:
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.calls += 1

    def report(self) -> str:
        return (
            f"{self.calls} calls, {self.input_tokens} in / {self.output_tokens} out "
            f"({self.used}/{self.ceiling} of ceiling), {len(self.rejected)} rejected"
        )


def is_prescriptive(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    return any(phrase in lowered for phrase in PRESCRIPTIVE)


def _trim(text: str, max_words: int) -> str:
    words = text.split()
    return " ".join(words[:max_words])


def summarise_change(
    client,
    *,
    instrument_ref: str,
    section_key: str,
    old_body: str | None,
    new_body: str | None,
    budget: EnrichmentBudget,
) -> ChangeSummary | None:
    """Summarise one change. Returns None if unusable — never a partial result.

    Only public MAS clause text is sent.
    """
    if budget.exhausted:
        return None

    prompt = (
        f"Instrument: {instrument_ref}, clause {section_key}\n\n"
        f"PREVIOUS VERSION:\n{_trim(old_body or '(clause did not exist)', 400)}\n\n"
        f"NEW VERSION:\n{_trim(new_body or '(clause was removed)', 400)}"
    )

    try:
        response = client.messages.parse(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
            output_format=ChangeSummary,
        )
    except Exception as exc:  # noqa: BLE001 - one failure must not stop the batch
        log.warning("enrichment failed for %s %s: %s", instrument_ref, section_key, exc)
        return None

    budget.record(response.usage)
    result = response.parsed_output
    if result is None:
        return None

    # The filter runs on the model's output, not on our prompt's intentions.
    if is_prescriptive(result.summary) or is_prescriptive(result.action_hint):
        budget.rejected.append(f"{instrument_ref} {section_key}")
        log.info("rejected prescriptive summary for %s %s", instrument_ref, section_key)
        return None

    return ChangeSummary(
        summary=_trim(result.summary, 30),
        obligation_change=result.obligation_change,
        action_hint=_trim(result.action_hint or "", 20),
    )


def build_client():
    """Anthropic client, or None when no key is configured.

    Returning None rather than raising keeps enrichment strictly optional: the
    pipeline must run to completion with no API key at all.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic

    return anthropic.Anthropic()
