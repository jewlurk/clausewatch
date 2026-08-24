"""Smoke tests — prove the package imports and config loads. Real tests land with
the parser (T13) and differ (T19). CI must go green from day one so regressions are
visible immediately.
"""
from config import Config


def test_config_loads_from_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("CRAWLER_MIN_INTERVAL_SECONDS", "2")
    cfg = Config.from_env()
    assert cfg.supabase_url == "https://example.supabase.co"
    assert cfg.crawler_min_interval_seconds == 2.0


def test_crawler_interval_meets_brief_floor():
    # Brief §4.4: rate limit must be <= 1 request per 2 seconds.
    cfg = Config.from_env()
    assert cfg.crawler_min_interval_seconds >= 2.0
