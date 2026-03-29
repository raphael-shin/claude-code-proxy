from __future__ import annotations

import json

from token_service.handler import TokenServiceHandlerDependencies, handle_get_or_create_key
from tests.fakes import FakeRequestIdGenerator, InMemoryUserRepository


class DummyIssueService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def get_or_create_key(self, user_id: str, *, request_id: str) -> None:
        self.calls.append((user_id, request_id))
        raise AssertionError("issue service should not be called for an unregistered user")


def test_unregistered_username_returns_403_before_issue_lookup() -> None:
    dependencies = TokenServiceHandlerDependencies(
        user_repository=InMemoryUserRepository(),
        issue_service=DummyIssueService(),
        request_id_generator=FakeRequestIdGenerator("req-unregistered"),
    )

    response = handle_get_or_create_key(
        {
            "requestContext": {
                "identity": {
                    "userArn": "arn:aws:sts::123456789012:assumed-role/AWSReservedSSO_Dev/alice"
                }
            }
        },
        dependencies=dependencies,
    )

    body = json.loads(response["body"])
    assert response["statusCode"] == 403
    assert body["error"]["type"] == "user_not_registered"
    assert body["error"]["request_id"] == "req-unregistered"
    assert dependencies.issue_service.calls == []

