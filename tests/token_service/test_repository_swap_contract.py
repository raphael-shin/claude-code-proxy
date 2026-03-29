from __future__ import annotations

import json

from api.dependencies import build_token_service_dependencies
from models.domain import UserRecord
from repositories.user_repository import PostgresUserRepository
from repositories.virtual_key_repository import DynamoDbVirtualKeyCache, PostgresVirtualKeyRepository
from token_service.handler import handle_get_or_create_key
from tests.fakes import (
    FakeClock,
    FakeDynamoDbTable,
    FakeEncryptionService,
    FakePostgresConnection,
    FakeRequestIdGenerator,
    InMemoryUserRepository,
    InMemoryVirtualKeyCacheRepository,
    InMemoryVirtualKeyLedgerRepository,
)


def _build_fake_dependency_bundle():
    user_repository = InMemoryUserRepository()
    user_repository.add_user(
        UserRecord(id="user-1", email="dev@example.com", display_name="Dev One"),
        username="alice",
    )
    return build_token_service_dependencies(
        user_repository=user_repository,
        virtual_key_repository=InMemoryVirtualKeyLedgerRepository(),
        virtual_key_cache=InMemoryVirtualKeyCacheRepository(),
        encryption_service=FakeEncryptionService(),
        clock=FakeClock(),
        request_id_generator=FakeRequestIdGenerator("req-contract"),
        key_generator=lambda: "vk_contract",
    )


def _build_storage_dependency_bundle():
    postgres = FakePostgresConnection()
    postgres.seed_user(
        UserRecord(id="user-1", email="dev@example.com", display_name="Dev One"),
        username="alice",
    )
    return build_token_service_dependencies(
        user_repository=PostgresUserRepository(postgres),
        virtual_key_repository=PostgresVirtualKeyRepository(postgres),
        virtual_key_cache=DynamoDbVirtualKeyCache(FakeDynamoDbTable()),
        encryption_service=FakeEncryptionService(),
        clock=FakeClock(),
        request_id_generator=FakeRequestIdGenerator("req-contract"),
        key_generator=lambda: "vk_contract",
    )


def test_token_service_contract_is_swappable_between_fake_and_storage_backends() -> None:
    event = {
        "requestContext": {
            "identity": {
                "userArn": "arn:aws:sts::123456789012:assumed-role/AWSReservedSSO_Dev/alice"
            }
        }
    }

    fake_response = handle_get_or_create_key(event, dependencies=_build_fake_dependency_bundle())
    storage_response = handle_get_or_create_key(event, dependencies=_build_storage_dependency_bundle())
    fake_body = json.loads(fake_response["body"])
    storage_body = json.loads(storage_response["body"])

    assert fake_response["statusCode"] == 200
    assert storage_response["statusCode"] == 200
    assert fake_body["virtual_key"] == storage_body["virtual_key"] == "vk_contract"
    assert fake_body["user_id"] == storage_body["user_id"] == "user-1"
    assert fake_body["key_prefix"] == storage_body["key_prefix"]
    assert fake_body["request_id"] == storage_body["request_id"] == "req-contract"
    assert isinstance(fake_body["key_id"], str) and fake_body["key_id"]
    assert isinstance(storage_body["key_id"], str) and storage_body["key_id"]
