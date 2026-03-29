from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from models.domain import ModelAliasRuleRecord


@runtime_checkable
class ModelAliasRepository(Protocol):
    def list_alias_rules(self) -> Sequence[ModelAliasRuleRecord]: ...

