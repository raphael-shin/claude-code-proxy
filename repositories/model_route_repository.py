from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from models.domain import ModelRouteRecord


@runtime_checkable
class ModelRouteRepository(Protocol):
    def list_model_routes(self) -> Sequence[ModelRouteRecord]: ...

