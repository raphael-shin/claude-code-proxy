from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from models.domain import BudgetPolicyRecord, PolicyRecord


@runtime_checkable
class PolicyRepository(Protocol):
    def list_policies_for_subject(self, *, user_id: str, groups: Sequence[str], department: str | None) -> Sequence[PolicyRecord]: ...

    def list_budget_policies_for_subject(self, *, user_id: str, team_ids: Sequence[str]) -> Sequence[BudgetPolicyRecord]: ...

