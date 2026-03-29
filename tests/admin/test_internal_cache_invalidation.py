from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import AppDependencies
from api.internal_ops import CacheInvalidationService
from models.domain import UserRecord, VirtualKeyCacheEntry, VirtualKeyRecord, VirtualKeyStatus
from security.encryption import SimpleEnvelopeEncryption
from security.keys import get_virtual_key_prefix, hash_virtual_key
from tests.fakes.fake_repositories import (
    InMemoryUserRepository,
    InMemoryVirtualKeyCacheRepository,
    InMemoryVirtualKeyLedgerRepository,
)
from token_service.issue_service import TokenIssueService


def test_internal_cache_invalidation_forces_next_lookup_back_to_ledger() -> None:
    now = datetime(2026, 3, 29, tzinfo=timezone.utc)
    encryption = SimpleEnvelopeEncryption()
    user = UserRecord(id="user-1", email="alice@example.com", display_name="Alice")
    virtual_key = "vk_cached_1234567890"
    key_record = VirtualKeyRecord(
        id="key-1",
        user_id=user.id,
        key_hash=hash_virtual_key(virtual_key),
        encrypted_key_blob=encryption.encrypt(virtual_key),
        key_prefix=get_virtual_key_prefix(virtual_key),
        status=VirtualKeyStatus.ACTIVE,
        created_at=now,
    )

    user_repository = InMemoryUserRepository()
    user_repository.add_user(user)
    ledger_repository = InMemoryVirtualKeyLedgerRepository()
    ledger_repository.seed(key_record)
    cache_repository = InMemoryVirtualKeyCacheRepository()
    cache_repository.seed(
        VirtualKeyCacheEntry(
            user_id=user.id,
            virtual_key_id=key_record.id,
            encrypted_key_ref=key_record.encrypted_key_blob,
            key_prefix=key_record.key_prefix,
            status=VirtualKeyStatus.ACTIVE,
            ttl=int((now + timedelta(minutes=5)).timestamp()),
        )
    )
    dependencies = AppDependencies(
        internal_cache_ops_service=CacheInvalidationService(virtual_key_cache=cache_repository),
        internal_ops_token="internal-secret",
    )
    client = TestClient(create_app(dependencies))
    issue_service = TokenIssueService(
        user_repository=user_repository,
        virtual_key_repository=ledger_repository,
        virtual_key_cache=cache_repository,
        encryption_service=encryption,
        clock=lambda: now,
    )

    denied_response = client.post(
        "/internal/cache/invalidate",
        json={"user_id": user.id},
    )
    invalidate_response = client.post(
        "/internal/cache/invalidate",
        headers={"X-Internal-Token": "internal-secret"},
        json={"user_id": user.id},
    )
    result = issue_service.get_or_create_key(user.id, request_id="req-cache-invalidate")

    assert denied_response.status_code == 403
    assert invalidate_response.status_code == 202
    assert cache_repository.invalidated_user_ids == [user.id]
    assert result.source.value == "reused"
    assert user_repository.get_user_calls == [user.id]
    assert ledger_repository.get_active_key_calls == [user.id]
