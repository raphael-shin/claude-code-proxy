from __future__ import annotations

from datetime import datetime, timezone

from proxy.rate_limiter import InMemoryRateLimiter
from tests.fakes import FakeClock


def test_rate_limiter_blocks_per_user_with_retry_after() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
    limiter = InMemoryRateLimiter(requests_per_minute=2, clock=clock)

    first = limiter.check("user-1")
    second = limiter.check("user-1")
    third = limiter.check("user-1")
    other_user = limiter.check("user-2")

    assert first.allowed is True
    assert first.remaining_requests == 1

    assert second.allowed is True
    assert second.remaining_requests == 0

    assert third.allowed is False
    assert third.retry_after_seconds == 60
    assert third.remaining_requests == 0

    assert other_user.allowed is True
    assert other_user.remaining_requests == 1

    clock.advance(seconds=59)
    still_limited = limiter.check("user-1")
    assert still_limited.allowed is False
    assert still_limited.retry_after_seconds == 1

    clock.advance(seconds=1)
    reset_window = limiter.check("user-1")
    assert reset_window.allowed is True
    assert reset_window.retry_after_seconds is None
    assert reset_window.remaining_requests == 1
