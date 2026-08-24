"""Differ tests, including the renumbering test the brief calls out (§12).

The renumbering case is the whole reason this is a product and not a PDF diff: an
inserted clause must not make every clause below it look changed.
"""
from dataclasses import dataclass
from pathlib import Path

import pytest

from diff.delta import ADDED, MODIFIED, REMOVED, RENUMBERED, compute_delta
from diff.diff_html import diff_html
from diff.severity import score_severity
from diff.similarity import similarity, trigrams
from parse.sections import parse_pdf

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass
class FakeSection:
    section_key: str
    body: str

    @property
    def body_sha256(self) -> str:
        import hashlib

        return hashlib.sha256(self.body.encode()).hexdigest()


# ---------- similarity ----------


def test_trigrams_match_pg_trgm_padding():
    # pg_trgm pads each word with two leading and one trailing space.
    assert trigrams("cat") == {"  c", " ca", "cat", "at "}


def test_similarity_identical_is_one():
    assert similarity("a bank shall act", "a bank shall act") == 1.0


def test_similarity_unrelated_is_low():
    assert similarity("a bank shall verify identity", "penguins eat fish") < 0.2


def test_similarity_is_symmetric():
    a, b = "the bank shall act", "the bank must act"
    assert similarity(a, b) == similarity(b, a)


# ---------- severity ----------


def test_whitespace_only_change_is_cosmetic():
    assert score_severity("the  bank shall act", "the bank shall act") == 1


def test_punctuation_only_change_is_cosmetic():
    assert score_severity("as set out in 6:", "as set out in 6 -") == 1


def test_word_reorder_is_cosmetic_extraction_artifact():
    assert score_severity("party international officials", "party officials international") == 1


def test_added_modal_raises_severity():
    base = score_severity("the bank may act", "the bank may act now")
    stronger = score_severity("the bank may act", "the bank shall act")
    assert stronger > base


def test_changed_threshold_raises_severity():
    assert score_severity("limit is 5,000", "limit is 20,000") >= 4


def test_severity_is_capped():
    assert 1 <= score_severity("a 5 shall", "a 20 shall must prohibited 1 January 2027") <= 5


# ---------- diff_html ----------


def test_diff_html_marks_insertions_and_deletions():
    out = diff_html("the bank shall act", "the bank must act")
    assert "<del>shall</del>" in out
    assert "<ins>must</ins>" in out


def test_diff_html_escapes_untrusted_pdf_text():
    # Source is an uncontrolled PDF; a clause containing markup must not break out.
    out = diff_html("safe", "<script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


# ---------- compute_delta ----------


def test_unchanged_clauses_emit_nothing():
    a = [FakeSection("1.1", "the bank shall act")]
    b = [FakeSection("1.1", "the bank shall act")]
    assert compute_delta(a, b) == []


def test_modified_clause_is_reported_once():
    a = [FakeSection("1.1", "the bank shall verify the customer identity records")]
    b = [FakeSection("1.1", "the bank shall verify the customer identity documents")]
    deltas = compute_delta(a, b)
    assert len(deltas) == 1
    assert deltas[0].op == MODIFIED


def test_added_and_removed_are_detected():
    a = [FakeSection("1.1", "alpha clause about customer due diligence measures")]
    b = [FakeSection("1.1", "alpha clause about customer due diligence measures"),
         FakeSection("1.2", "beta clause concerning suspicious transaction reporting")]
    ops = {d.op for d in compute_delta(a, b)}
    assert ops == {ADDED}

    ops_back = {d.op for d in compute_delta(b, a)}
    assert ops_back == {REMOVED}


def test_renumbering_does_not_produce_phantom_modifications():
    """§12: insert a clause mid-document and renumber below.

    Expect exactly 1 ADDED + N RENUMBERED and zero MODIFIED. Without Pass 2 this
    reports every shifted clause as changed, which is what destroys credibility.
    """
    bodies = [
        "the bank shall establish and maintain policies for customer due diligence",
        "the bank shall identify each customer and verify the customer identity",
        "the bank shall screen customers against relevant sanctions lists regularly",
        "the bank shall report suspicious transactions to the authority promptly",
    ]
    old = [FakeSection(f"6.{i + 1}", body) for i, body in enumerate(bodies)]

    inserted = "the bank shall assess money laundering risk before onboarding"
    new = [
        FakeSection("6.1", bodies[0]),
        FakeSection("6.2", inserted),
        FakeSection("6.3", bodies[1]),
        FakeSection("6.4", bodies[2]),
        FakeSection("6.5", bodies[3]),
    ]

    deltas = compute_delta(old, new)
    ops = [d.op for d in deltas]
    assert ops.count(ADDED) == 1
    assert ops.count(RENUMBERED) == 3
    assert ops.count(MODIFIED) == 0
    assert ops.count(REMOVED) == 0

    renumbered = {(d.old_section_key, d.new_section_key) for d in deltas if d.op == RENUMBERED}
    assert renumbered == {("6.2", "6.3"), ("6.3", "6.4"), ("6.4", "6.5")}


def test_compute_delta_is_idempotent():
    old = parse_pdf(FIXTURES / "626_2024.pdf")
    new = parse_pdf(FIXTURES / "626_2025.pdf")
    first = compute_delta(old, new)
    second = compute_delta(old, new)
    assert [(d.op, d.old_section_key, d.new_section_key) for d in first] == [
        (d.op, d.old_section_key, d.new_section_key) for d in second
    ]


# ---------- G1: real documents ----------


@pytest.fixture(scope="module")
def real_deltas():
    old = parse_pdf(FIXTURES / "626_2024.pdf")
    new = parse_pdf(FIXTURES / "626_2025.pdf")
    return compute_delta(old, new)


def test_real_amendment_reports_a_plausible_number_of_changes(real_deltas):
    # MAS's own tracked-changes document marks 22 clauses. A differ reporting ~140
    # (the whole document) or ~2 is broken; this pins the order of magnitude.
    assert 10 <= len(real_deltas) <= 35


def test_real_amendment_detects_the_known_new_clauses(real_deltas):
    # 6.14A-D were genuinely inserted in the 30 June 2025 amendment.
    added = {d.new_section_key for d in real_deltas if d.op == ADDED}
    assert {"6.14A", "6.14B", "6.14C", "6.14D"} <= added


def test_no_delta_is_below_severity_two(real_deltas):
    assert all(d.severity >= 2 for d in real_deltas)
