from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, model_validator

from api.admin_auth import require_admin_write
from models.domain import BudgetMetricType, BudgetPeriodType, BudgetPolicyRecord, UserRecord
from repositories.user_repository import UserRepository

router = APIRouter()


class BudgetPolicyCreateRequest(BaseModel):
    id: str
    period_type: BudgetPeriodType
    metric_type: BudgetMetricType
    limit_value: int
    soft_limit_percent: int
    hard_limit_percent: int

    @model_validator(mode="after")
    def validate_percent_thresholds(self) -> BudgetPolicyCreateRequest:
        if self.soft_limit_percent > self.hard_limit_percent:
            raise ValueError("soft_limit_percent must be less than or equal to hard_limit_percent.")
        if self.hard_limit_percent > 100:
            raise ValueError("hard_limit_percent must be less than or equal to 100.")
        return self


class BudgetPolicyStore(Protocol):
    def create_policy(self, policy: BudgetPolicyRecord) -> None: ...


class BudgetPolicyAdminService:
    def __init__(
        self,
        *,
        user_repository: UserRepository,
        store: BudgetPolicyStore,
    ) -> None:
        self._user_repository = user_repository
        self._store = store

    def create_user_policy(
        self,
        *,
        user_id: str,
        request: BudgetPolicyCreateRequest,
    ) -> BudgetPolicyRecord:
        user = self._require_user(user_id)
        if not user.is_active:
            raise HTTPException(
                status_code=400,
                detail="Cannot create budget policy for inactive user.",
            )

        policy = BudgetPolicyRecord(
            id=request.id,
            scope_type="user",
            scope_id=user_id,
            period_type=request.period_type,
            metric_type=request.metric_type,
            limit_value=request.limit_value,
            soft_limit_percent=request.soft_limit_percent,
            hard_limit_percent=request.hard_limit_percent,
        )
        self._store.create_policy(policy)
        return policy

    def _require_user(self, user_id: str) -> UserRecord:
        user = self._user_repository.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found.")
        return user


@router.post("/admin/users/{user_id}/budget-policies", status_code=201)
def create_user_budget_policy(
    user_id: str,
    request: Request,
    payload: BudgetPolicyCreateRequest,
) -> dict[str, object]:
    require_admin_write(request)
    service = _budget_policy_service(request)
    policy = service.create_user_policy(user_id=user_id, request=payload)
    return jsonable_encoder(policy)


def _budget_policy_service(request: Request) -> BudgetPolicyAdminService:
    service = request.app.state.dependencies.budget_policy_service
    if service is None:
        raise HTTPException(status_code=500, detail="Budget policy service is not configured.")
    return service
