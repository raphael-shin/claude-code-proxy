from __future__ import annotations

from datetime import date
from typing import Protocol, runtime_checkable

from models.domain import ModelPricingRecord


@runtime_checkable
class PricingRepository(Protocol):
    def get_active_pricing(self, *, model_id: str, at_date: date | None = None) -> ModelPricingRecord | None: ...

    def reload(self) -> None: ...
