"""Enrichment guard tests.

The prescriptive-language filter is a legal control, not a quality nicety: Legal
Profession Act 1966 s.33 makes advising on legal obligations a criminal offence for
the unqualified. It gets tested like one.
"""
import pytest

from enrich.summarise import (
    MIN_SEVERITY,
    SYSTEM_PROMPT,
    ChangeSummary,
    EnrichmentBudget,
    is_prescriptive,
)


@pytest.mark.parametrize(
    "text",
    [
        "You must now verify the beneficial owner.",
        "You should update your onboarding policy.",
        "Firms are required to screen against the new list.",
        "Banks must retain records for a further year.",
        "We recommend reviewing your controls.",
        "Ensure that you document the assessment.",
    ],
)
def test_advice_is_rejected(text):
    assert is_prescriptive(text)


@pytest.mark.parametrize(
    "text",
    [
        "The clause now requires verification within five days.",
        "A numeric threshold changed from S$20,000 to S$5,000.",
        "The definition of beneficial owner was widened.",
        "Paragraph 6.14 was replaced by 6.14A to 6.14D.",
        "",
    ],
)
def test_description_is_allowed(text):
    assert not is_prescriptive(text)


def test_filter_ignores_whitespace_and_case():
    assert is_prescriptive("YOU   MUST\n  do this")


def test_prompt_forbids_interpretation():
    # The prompt is the first line of defence and must stay descriptive-only.
    assert "Do NOT advise on compliance" in SYSTEM_PROMPT
    assert "Do NOT interpret legal effect" in SYSTEM_PROMPT


def test_llm_only_sees_material_changes():
    # §10: cosmetic changes never reach a paid API call.
    assert MIN_SEVERITY == 3


def test_budget_stops_at_the_ceiling():
    budget = EnrichmentBudget(ceiling=1000)

    class Usage:
        input_tokens, output_tokens = 600, 300

    budget.record(Usage())
    assert not budget.exhausted
    budget.record(Usage())
    assert budget.exhausted  # 1800 > 1000 — enrichment stops, pipeline continues


def test_schema_defaults_action_hint_to_empty():
    s = ChangeSummary(summary="Threshold changed.", obligation_change=True)
    assert s.action_hint == ""
