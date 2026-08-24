"""Parser tests against four real MAS Notice 626 PDFs (2015, 2022, 2024, 2025).

Every assertion here encodes a bug found on real documents. Synthetic PDFs would have
passed while the parser silently dropped 30% of the corpus.
"""
import itertools
from pathlib import Path

import pytest

from parse.normalise import normalise
from parse.sections import parse_pdf, parse_sections, sort_key

FIXTURES = Path(__file__).parent / "fixtures"
PDFS = sorted(FIXTURES.glob("*.pdf"))


@pytest.fixture(scope="module")
def sections_2025():
    return parse_pdf(FIXTURES / "626_2025.pdf")


# ---------- normalisation ----------


def test_normalise_collapses_justified_whitespace():
    # MAS PDFs are justified; identical text reflows with different gap widths.
    assert normalise("PREVENTION  OF   MONEY") == "PREVENTION OF MONEY"


def test_normalise_strips_running_header():
    # Real header form is "[MAS Notice 626 (Amendment) 2025]", not the narrower
    # "[MAS Notice 626]" the brief assumed.
    assert "MAS Notice" not in normalise("text [MAS Notice 626 (Amendment) 2025] more")


def test_normalise_canonicalises_quotes_and_dashes():
    assert normalise("“FSM Act” – the") == '"FSM Act" - the'


def test_normalise_is_idempotent():
    once = normalise("  a  “b”  [MAS Notice 626] c ")
    assert normalise(once) == once


# ---------- clause keys ----------


def test_sort_key_orders_lettered_inserts_after_base():
    assert sort_key("6.14") < sort_key("6.14A") < sort_key("6.14B") < sort_key("6.15")


def test_sort_key_is_numeric_not_lexical():
    # '6.9' must sort before '6.14' — string comparison gets this wrong.
    assert sort_key("6.9") < sort_key("6.14")


# ---------- segmentation on real documents ----------


@pytest.mark.parametrize("pdf", PDFS, ids=lambda p: p.name)
def test_no_duplicate_section_keys(pdf):
    # sections has `unique (version_id, section_key)` — duplicates break ingest.
    keys = [s.section_key for s in parse_pdf(pdf)]
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize("pdf", PDFS, ids=lambda p: p.name)
def test_parses_a_full_document(pdf):
    sections = parse_pdf(pdf)
    assert len(sections) > 100
    assert sections[0].section_key == "1.1"


@pytest.mark.parametrize("pdf", PDFS, ids=lambda p: p.name)
def test_no_page_furniture_leaks_into_bodies(pdf):
    for section in parse_pdf(pdf):
        assert "[MAS Notice" not in section.body
        assert "Page " not in section.body or " of " not in section.body


def test_captures_clauses_whose_number_is_on_its_own_line(sections_2025):
    # 39 of ~146 clauses put the number on one line and the body beneath. Requiring
    # same-line body silently dropped every clause before 6.1.
    by_key = {s.section_key: s for s in sections_2025}
    assert by_key["1.1"].body.startswith("This Notice is issued under section 16")
    assert "1 April 2024" in by_key["1.2"].body


def test_lettered_amendment_clauses_are_distinct(sections_2025):
    # MAS inserts amendments as 6.14A..D instead of renumbering. Truncating the letter
    # collapsed four clauses into one key and left a stray "A"/"B" heading each body.
    by_key = {s.section_key: s for s in sections_2025}
    for key in ("6.14", "6.14A", "6.14B", "6.14C", "6.14D"):
        assert key in by_key
    assert by_key["6.14A"].body.startswith("For the purposes of paragraph 6.14")
    assert not by_key["6.14B"].body.startswith("B ")


def test_wrapped_cross_reference_is_not_a_new_clause(sections_2025):
    # "...paragraphs 11.3 / to 11.8..." wraps so a line begins with "11.3". Clause
    # numbers advance monotonically, so a backwards number is a reference, not a clause.
    bodies = [s.body for s in sections_2025 if s.section_key == "11.3"]
    assert len(bodies) == 1
    assert not bodies[0].startswith("to 11.8")


def test_no_gaps_in_clause_numbering(sections_2025):
    """A gap means a clause was missed — the T13 accuracy check."""
    keys = [sort_key(s.section_key) for s in sections_2025]
    gaps = []
    for prev, cur in itertools.pairwise(keys):
        same_chapter = len(prev[0]) == 2 and len(cur[0]) == 2 and prev[0][0] == cur[0][0]
        if same_chapter and not prev[1] and not cur[1] and cur[0][1] - prev[0][1] > 1:
            gaps.append((prev, cur))
    assert gaps == []


def test_headings_are_attached_and_not_swallowed(sections_2025):
    by_key = {s.section_key: s for s in sections_2025}
    assert by_key["1.1"].heading == "INTRODUCTION"
    assert by_key["2.1"].heading == "DEFINITIONS"
    assert all(s.heading for s in sections_2025)


def test_ordinal_is_document_order(sections_2025):
    assert [s.ordinal for s in sections_2025] == list(range(len(sections_2025)))


# ---------- hashing (the differ depends on this) ----------


def test_identical_text_hashes_equal_despite_whitespace_noise():
    a = parse_sections("1.1  the  bank   shall  act")[0]
    b = parse_sections("1.1 the bank shall act")[0]
    assert a.body_sha256 == b.body_sha256


def test_changed_text_hashes_differently():
    a = parse_sections("1.1 the bank shall act")[0]
    b = parse_sections("1.1 the bank may act")[0]
    assert a.body_sha256 != b.body_sha256


def test_unchanged_clauses_across_real_versions_hash_equal():
    """The differ's Pass 1 relies on this: unchanged clauses must be byte-identical
    across two separately-published PDFs, or every clause looks MODIFIED."""
    v2024 = {s.section_key: s for s in parse_pdf(FIXTURES / "626_2024.pdf")}
    v2025 = {s.section_key: s for s in parse_pdf(FIXTURES / "626_2025.pdf")}
    shared = set(v2024) & set(v2025)
    identical = sum(1 for k in shared if v2024[k].body_sha256 == v2025[k].body_sha256)
    # 2025 was a targeted amendment: the vast majority of clauses are untouched.
    assert identical / len(shared) > 0.80
