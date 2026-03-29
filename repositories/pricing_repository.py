from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable


@runtime_checkable
class PricingRepository(Protocol):
    def get_effective_price(self, *, model_id: str, at_date: date | None = None) -> float | None: ...

