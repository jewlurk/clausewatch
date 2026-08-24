"""The rate limiter is a legal/etiquette control (brief §4.4), so it gets real tests.

Uses injected clocks — the suite must stay fast and must not actually sleep.
"""
import pytest

from crawler.ratelimit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds


def test_first_request_does_not_wait():
    c = FakeClock()
    rl = RateLimiter(2.0)
    assert rl.acquire(_sleep=c.sleep, _now=c.now) == 0.0
    assert c.slept == []


def test_back_to_back_requests_wait_full_interval():
    c = FakeClock()
    rl = RateLimiter(2.0)
    rl.acquire(_sleep=c.sleep, _now=c.now)
    waited = rl.acquire(_sleep=c.sleep, _now=c.now)
    assert waited == pytest.approx(2.0)
    assert c.slept == [pytest.approx(2.0)]


def test_no_wait_when_caller_was_already_slow():
    c = FakeClock()
    rl = RateLimiter(2.0)
    rl.acquire(_sleep=c.sleep, _now=c.now)
    c.t += 5.0  # caller spent 5s doing other work
    assert rl.acquire(_sleep=c.sleep, _now=c.now) == 0.0
    assert c.slept == []


def test_sustained_rate_never_exceeds_one_per_interval():
    c = FakeClock()
    rl = RateLimiter(2.0)
    start = c.t
    for _ in range(10):
        rl.acquire(_sleep=c.sleep, _now=c.now)
    # 10 requests at >=2s spacing must span at least 18s (9 gaps).
    assert c.t - start >= 18.0


def test_rejects_nonpositive_interval():
    with pytest.raises(ValueError):
        RateLimiter(0)
