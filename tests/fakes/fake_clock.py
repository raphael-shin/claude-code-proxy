from __future__ import annotations

from datetime import datetime, timedelta, timezone


class FakeClock:
    def __init__(self, now: datetime | None = None) -> None:
        self._now = now or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self._now

    def advance(self, *, seconds: int = 0, minutes: int = 0) -> None:
        self._now += timedelta(seconds=seconds, minutes=minutes)

