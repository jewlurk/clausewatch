"""The cost model and health thresholds (cost.py, T29 §13).

The whole reason this arithmetic is a separate pure module is so the numbers that
decide whether to raise a budget alarm can be tested without a database or a network.
"""
from __future__ import annotations

import cost


def test_haiku_price_matches_the_published_rate():
    """1M in + 1M out at USD 1.00 / USD 5.00 = USD 6.00 (checked 2026-08-26)."""
    assert cost.llm_cost_usd("claude-haiku-4-5", 1_000_000, 1_000_000) == 6.00


def test_the_backfill_run_cost_is_a_believable_figure():
    """The 26 Aug backfill billed ~399,517 in / 110,199 out on Haiku."""
    usd = cost.llm_cost_usd("claude-haiku-4-5", 399_517, 110_199)
    assert 0.90 < usd < 1.05  # roughly USD 0.95


def test_an_unpriced_model_returns_none_not_zero():
    """A silent zero would read as 'free' on a budget page — the one wrong reading."""
    assert cost.llm_cost_usd("some-future-model", 1_000_000, 1_000_000) is None


def test_db_alarm_trips_at_350_not_before():
    assert not cost.db_threshold(349).breached
    assert cost.db_threshold(350).breached
    assert cost.db_threshold(351).breached


def test_db_threshold_reports_percent_of_the_500mb_limit():
    t = cost.db_threshold(250)
    assert round(t.pct_of_limit) == 50
    assert "MB" in t.line()


def test_a_breached_threshold_line_is_marked():
    assert "ALARM" in cost.db_threshold(400).line()
    assert "ALARM" not in cost.db_threshold(100).line()


def test_r2_threshold_converts_bytes_to_gb_and_alarms_at_7():
    assert not cost.r2_threshold(6_000_000_000).breached
    assert cost.r2_threshold(7_000_000_000).breached


def test_current_r2_footprint_is_nowhere_near_the_alarm():
    """~40 MB today; the tripwire is for a MAS site restructure, not normal growth."""
    t = cost.r2_threshold(40_000_000)
    assert not t.breached
    assert t.pct_of_limit < 1
