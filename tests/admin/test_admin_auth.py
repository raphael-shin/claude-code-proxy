from __future__ import annotations

from fastapi.testclient import TestClient

from api.admin_users import UserProvisioningService
from api.app import create_app
from api.dependencies import AppDependencies
from tests.admin.support import (
    InMemoryAdminIdentityRepository,
    InMemoryUsageQueryService,
    InMemoryUserProvisioningStore,
    admin_headers,
)


def test_admin_auth_uses_allowlist_and_keeps_auditor_read_only() -> None:
    dependencies = AppDependencies(
        admin_identity_repository=InMemoryAdminIdentityRepository(
            {
                "principal:operator": "operator",
                "principal:auditor": "auditor",
            }
        ),
        usage_query_service=InMemoryUsageQueryService(),
        user_provisioning_service=UserProvisioningService(
            store=InMemoryUserProvisioningStore()
        ),
    )
    client = TestClient(create_app(dependencies))

    non_admin_response = client.get("/admin/usage", headers=admin_headers("principal:guest"))
    auditor_read_response = client.get(
        "/admin/usage",
        headers=admin_headers("principal:auditor"),
    )
    auditor_write_response = client.post(
        "/admin/users",
        headers=admin_headers("principal:auditor"),
        json={
            "username": "alice",
            "user_id": "user-1",
            "email": "alice@example.com",
            "display_name": "Alice",
        },
    )

    assert non_admin_response.status_code == 403
    assert auditor_read_response.status_code == 200
    assert auditor_read_response.json() == {"items": []}
    assert auditor_write_response.status_code == 403
