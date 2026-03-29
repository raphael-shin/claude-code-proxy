from __future__ import annotations

from fastapi.testclient import TestClient

from api.admin_budget_policies import BudgetPolicyAdminService
from api.admin_users import UserProvisioningService
from api.app import create_app
from api.dependencies import AppDependencies
from tests.admin.support import (
    InMemoryAdminIdentityRepository,
    InMemoryBudgetPolicyStore,
    InMemoryUserProvisioningStore,
    ProvisionedUserRepository,
    admin_headers,
)


def test_user_provisioning_creates_user_and_identity_mapping_and_rejects_inactive_budget_policy() -> None:
    provisioning_store = InMemoryUserProvisioningStore()
    budget_policy_store = InMemoryBudgetPolicyStore()
    user_repository = ProvisionedUserRepository(provisioning_store)
    dependencies = AppDependencies(
        admin_identity_repository=InMemoryAdminIdentityRepository(
            {"principal:operator": "operator"}
        ),
        user_provisioning_service=UserProvisioningService(store=provisioning_store),
        budget_policy_service=BudgetPolicyAdminService(
            user_repository=user_repository,
            store=budget_policy_store,
        ),
    )
    client = TestClient(create_app(dependencies))

    create_response = client.post(
        "/admin/users",
        headers=admin_headers("principal:operator"),
        json={
            "username": "alice",
            "user_id": "user-1",
            "email": "alice@example.com",
            "display_name": "Alice",
            "groups": ["eng"],
        },
    )
    inactive_response = client.post(
        "/admin/users",
        headers=admin_headers("principal:operator"),
        json={
            "username": "bob",
            "user_id": "user-2",
            "email": "bob@example.com",
            "display_name": "Bob",
            "is_active": False,
        },
    )
    budget_response = client.post(
        "/admin/users/user-2/budget-policies",
        headers=admin_headers("principal:operator"),
        json={
            "id": "budget-1",
            "period_type": "day",
            "metric_type": "tokens",
            "limit_value": 1000,
            "soft_limit_percent": 50,
            "hard_limit_percent": 80,
        },
    )

    assert create_response.status_code == 201
    assert inactive_response.status_code == 201
    assert "user-1" in provisioning_store.users
    assert provisioning_store.mappings["alice"].user_id == "user-1"
    assert budget_response.status_code == 400
    assert budget_response.json()["detail"] == "Cannot create budget policy for inactive user."
    assert budget_policy_store.saved_policies == []
