from __future__ import annotations

from fastapi.testclient import TestClient

from api.admin_budget_policies import BudgetPolicyAdminService
from api.app import create_app
from api.dependencies import AppDependencies
from models.domain import UserRecord
from tests.admin.support import (
    InMemoryAdminIdentityRepository,
    InMemoryBudgetPolicyStore,
    admin_headers,
)


class ActiveUserRepository:
    def get_user_id_for_username(self, username: str) -> str | None:
        return None

    def get_user(self, user_id: str) -> UserRecord | None:
        return UserRecord(id=user_id, email="owner@example.com", display_name="Owner")


def test_budget_policy_validation_enforces_soft_and_hard_limits() -> None:
    dependencies = AppDependencies(
        admin_identity_repository=InMemoryAdminIdentityRepository(
            {"principal:operator": "operator"}
        ),
        budget_policy_service=BudgetPolicyAdminService(
            user_repository=ActiveUserRepository(),
            store=InMemoryBudgetPolicyStore(),
        ),
    )
    client = TestClient(create_app(dependencies))

    invalid_order = client.post(
        "/admin/users/user-1/budget-policies",
        headers=admin_headers("principal:operator"),
        json={
            "id": "budget-1",
            "period_type": "day",
            "metric_type": "tokens",
            "limit_value": 1000,
            "soft_limit_percent": 90,
            "hard_limit_percent": 80,
        },
    )
    invalid_ceiling = client.post(
        "/admin/users/user-1/budget-policies",
        headers=admin_headers("principal:operator"),
        json={
            "id": "budget-2",
            "period_type": "month",
            "metric_type": "cost_usd",
            "limit_value": 100,
            "soft_limit_percent": 50,
            "hard_limit_percent": 110,
        },
    )

    assert invalid_order.status_code == 422
    assert invalid_ceiling.status_code == 422
