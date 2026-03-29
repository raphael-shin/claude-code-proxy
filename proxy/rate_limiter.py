from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

Clock = Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    status_code: int | None = None
    retry_after_seconds: int | None = None
    remaining_requests: int | None = None


class InMemoryRateLimiter:
    def __init__(self, *, requests_per_minute: int, clock: Clock) -> None:
        self._requests_per_minute = max(1, requests_per_minute)
        self._clock = clock
        self._request_windows: dict[str, list[datetime]] = {}

    def check(self, user_id: str) -> RateLimitDecision:
        now = self._clock()
        window_start = now.replace(second=0, microsecond=0)
        window_end = window_start + timedelta(minutes=1)

        active_requests = [
            timestamp
            for timestamp in self._request_windows.get(user_id, [])
            if timestamp >= window_start
        ]
        self._request_windows[user_id] = active_requests

        if len(active_requests) >= self._requests_per_minute:
            retry_after = max(1, int((window_end - now).total_seconds()))
            return RateLimitDecision(
                allowed=False,
                status_code=429,
                retry_after_seconds=retry_after,
                remaining_requests=0,
            )

        active_requests.append(now)
        remaining_requests = max(0, self._requests_per_minute - len(active_requests))
        return RateLimitDecision(
            allowed=True,
            remaining_requests=remaining_requests,
        )
