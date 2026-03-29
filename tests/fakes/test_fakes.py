from __future__ import annotations

from datetime import datetime, timezone

from models.domain import UserRecord
from tests.fakes import FakeBedrockClient, FakeClock, FakeDynamoDbTable, FakePostgresConnection, FakeRequestIdGenerator


def test_fake_clock_can_advance() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))

    clock.advance(minutes=5)

    assert clock().isoformat() == "2026-01-01T00:05:00+00:00"


def test_fake_request_id_generator_uses_seeded_values() -> None:
    generator = FakeRequestIdGenerator("req-a", "req-b")

    assert generator() == "req-a"
    assert generator() == "req-b"
    assert generator() == "req-3"


def test_fake_postgres_and_dynamodb_store_state() -> None:
    postgres = FakePostgresConnection()
    dynamodb = FakeDynamoDbTable()
    user = UserRecord(id="user-1", email="dev@example.com", display_name="Dev One")

    postgres.seed_user(user, username="alice")
    dynamodb.put_item({"user_id": "user-1", "ttl": 100, "status": "active", "key_prefix": "vk_x", "virtual_key_id": "key-1", "encrypted_key_ref": "enc::vk_x"})

    assert postgres.get_identity_mapping("alice") is not None
    assert dynamodb.get_item("user-1") is not None


def test_fake_bedrock_records_invocations() -> None:
    bedrock = FakeBedrockClient()

    response = bedrock.invoke({"model": "claude-sonnet"})

    assert response["ok"] is True
    assert bedrock.requests == [{"model": "claude-sonnet"}]

