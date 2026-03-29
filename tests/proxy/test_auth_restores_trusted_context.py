from __future__ import annotations

from datetime import datetime, timezone

from models.domain import UserRecord, VirtualKeyRecord, VirtualKeyStatus
from proxy.auth import ProxyAuthService
from security.keys import hash_virtual_key
from tests.fakes import InMemoryUserRepository, InMemoryVirtualKeyLedgerRepository


def test_auth_restores_trusted_context_from_virtual_key_only() -> None:
    user = UserRecord(
        id="user-123",
        email="trusted@example.com",
        display_name="Trusted User",
        department="platform",
        groups=("eng", "proxy-admin"),
        proxy_access_enabled=True,
        is_active=True,
    )
    user_repository = InMemoryUserRepository()
    user_repository.add_user(user)

    virtual_key = "vk_trusted_example"
    key_record = VirtualKeyRecord(
        id="vk-record-123",
        user_id=user.id,
        key_hash=hash_virtual_key(virtual_key),
        encrypted_key_blob="encrypted:vk_trusted_example",
        key_prefix="vk_truste",
        status=VirtualKeyStatus.ACTIVE,
        created_at=datetime(2026, 3, 29, tzinfo=timezone.utc),
    )
    virtual_key_repository = InMemoryVirtualKeyLedgerRepository()
    virtual_key_repository.seed(key_record)

    auth_service = ProxyAuthService(
        virtual_key_repository=virtual_key_repository,
        user_repository=user_repository,
    )

    authenticated = auth_service.authenticate(
        f"Bearer {virtual_key}",
        request_id="req-auth-2",
        headers={
            "X-User-Id": "forged-user",
            "X-User-Email": "forged@example.com",
        },
        body={
            "user_id": "body-user",
            "email": "body@example.com",
            "groups": ["forged-group"],
            "department": "finance",
        },
    )

    assert authenticated.request_id == "req-auth-2"
    assert authenticated.virtual_key_id == "vk-record-123"
    assert authenticated.key_hash == key_record.key_hash
    assert authenticated.key_prefix == "vk_truste"
    assert authenticated.user.user_id == user.id
    assert authenticated.user.email == "trusted@example.com"
    assert authenticated.user.groups == ("eng", "proxy-admin")
    assert authenticated.user.department == "platform"
    assert user_repository.get_user_calls == [user.id]
