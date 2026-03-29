from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import AppDependencies
from models.domain import AuditEventRecord, UsageEventRecord
from tests.admin.support import (
    InMemoryAdminIdentityRepository,
    InMemoryUsageQueryService,
    admin_headers,
)


def test_usage_and_audit_queries_filter_by_user_team_and_model() -> None:
    timestamp = datetime(2026, 3, 29, tzinfo=timezone.utc)
    usage_service = InMemoryUsageQueryService(
        usage_events=[
            UsageEventRecord(
                id="usage-match",
                request_id="req-1",
                user_id="user-1",
                user_email="alice@example.com",
                requested_model="claude-sonnet",
                resolved_model="anthropic.claude-sonnet-4-5-v1:0",
                pricing_catalog_id="pricing-1",
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                team_id="team-1",
                created_at=timestamp,
            ),
            UsageEventRecord(
                id="usage-other",
                request_id="req-2",
                user_id="user-2",
                user_email="bob@example.com",
                requested_model="claude-haiku",
                resolved_model="anthropic.claude-3-5-haiku-v1:0",
                pricing_catalog_id="pricing-2",
                input_tokens=5,
                output_tokens=5,
                total_tokens=10,
                team_id="team-2",
                created_at=timestamp,
            ),
        ],
        audit_events=[
            AuditEventRecord(
                id="audit-match",
                request_id="req-1",
                event_type="auth_success",
                actor_user_id="user-1",
                actor_user_email="alice@example.com",
                decision="allow",
                requested_model="claude-sonnet",
                resolved_model="anthropic.claude-sonnet-4-5-v1:0",
                team_id="team-1",
                created_at=timestamp,
            ),
            AuditEventRecord(
                id="audit-other",
                request_id="req-2",
                event_type="policy_denied",
                actor_user_id="user-2",
                actor_user_email="bob@example.com",
                decision="deny",
                requested_model="claude-haiku",
                resolved_model="anthropic.claude-3-5-haiku-v1:0",
                team_id="team-2",
                created_at=timestamp,
            ),
        ],
    )
    dependencies = AppDependencies(
        admin_identity_repository=InMemoryAdminIdentityRepository(
            {"principal:auditor": "auditor"}
        ),
        usage_query_service=usage_service,
    )
    client = TestClient(create_app(dependencies))

    usage_response = client.get(
        "/admin/usage",
        headers=admin_headers("principal:auditor"),
        params={"user_id": "user-1", "team_id": "team-1", "model": "claude-sonnet"},
    )
    audit_response = client.get(
        "/admin/audit-events",
        headers=admin_headers("principal:auditor"),
        params={"user_id": "user-1", "team_id": "team-1", "model": "claude-sonnet"},
    )

    assert usage_response.status_code == 200
    assert audit_response.status_code == 200
    assert [item["id"] for item in usage_response.json()["items"]] == ["usage-match"]
    assert [item["id"] for item in audit_response.json()["items"]] == ["audit-match"]
