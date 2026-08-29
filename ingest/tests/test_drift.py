"""Schema-drift invariants (drift.py, T31).

These are the tripwires for a MAS-side format change. The tests fix the two failure
modes that matter: a real structural break must fire CRITICAL, and a normal corpus must
stay silent — a drift alarm that cries wolf gets muted, and a muted alarm is worse than
none.
"""
from __future__ import annotations

from drift import (
    CRITICAL,
    WARNING,
    InstrumentHealth,
    check_corpus,
    check_instrument,
    has_critical,
)


def healthy(ref="Notice 626", **over) -> InstrumentHealth:
    base = {
        "external_ref": ref,
        "versions_total": 15,
        "consolidated_versions": 7,
        "dated_versions": 7,
        "latest_section_count": 146,
        "failed_parses": 0,
    }
    base.update(over)
    return InstrumentHealth(**base)


def test_a_normal_instrument_produces_no_findings():
    assert check_instrument(healthy()) == []


def test_discovery_drift_no_documents_at_all_is_critical():
    findings = check_instrument(healthy(versions_total=0, consolidated_versions=0,
                                        dated_versions=0, latest_section_count=0))
    assert len(findings) == 1
    assert findings[0].level == CRITICAL
    assert "discovery" in findings[0].message or "landing page" in findings[0].message


def test_parse_drift_documents_but_none_consolidated_is_critical():
    """PDFs still download, but none parses to a full notice — layout changed."""
    findings = check_instrument(healthy(versions_total=15, consolidated_versions=0,
                                        dated_versions=0, latest_section_count=0))
    assert any(f.level == CRITICAL and "consolidated" in f.message for f in findings)


def test_an_undersized_newest_version_is_critical():
    findings = check_instrument(healthy(latest_section_count=12))
    assert any(f.level == CRITICAL and "clauses" in f.message for f in findings)


def test_a_notice_that_is_genuinely_at_the_floor_is_fine():
    """65 clauses (TCA-N03 2009) is a real small notice, not drift."""
    assert check_instrument(healthy(latest_section_count=65)) == []


def test_date_extraction_drift_is_critical():
    findings = check_instrument(healthy(dated_versions=0))
    assert any(f.level == CRITICAL and "date" in f.message for f in findings)


def test_a_single_parse_failure_is_a_warning_not_critical():
    findings = check_instrument(healthy(failed_parses=1))
    assert findings and all(f.level == WARNING for f in findings)
    assert not has_critical(findings)


def test_a_missing_instrument_is_flagged_at_the_corpus_level():
    findings = check_corpus([healthy()], expected_instruments=11)
    assert any(f.level == CRITICAL and "expected 11" in f.message for f in findings)


def test_a_complete_healthy_corpus_is_silent():
    corpus = [healthy(ref=f"N{i}") for i in range(11)]
    assert check_corpus(corpus, expected_instruments=11) == []
