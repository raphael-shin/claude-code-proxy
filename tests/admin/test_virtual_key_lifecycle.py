from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api.admin_virtual_keys import VirtualKeyLifecycleService
from api.app import create_app
from api.dependencies import AppDependencies
from models.domain import UserRecord, VirtualKeyRecord, VirtualKeyStatus
from models.errors import ServiceError
from proxy.auth import ProxyAuthService
from security.encryption import SimpleEnvelopeEncryption
from security.keys import get_virtual_key_prefix, hash_virtual_key
from tests.admin.support import (
    InMemoryAdminIdentityRepository,
    InMemoryVirtualKeyAdminRepository,
    TrackingInvalidationDispatcher,
    admin_headers,
)
from tests.fakes.fake_repositories import InMemoryUserRepository


def test_virtual_key_revoke_disable_and_rotate_invalidate_caches_and_reject_old_keys() -> None:
    encryption = SimpleEnvelopeEncryption()
    repository = InMemoryVirtualKeyAdminRepository()
    dispatcher = TrackingInvalidationDispatcher()
    user_repository = InMemoryUserRepository()
    user = UserRecord(id="user-1", email="alice@example.com", display_name="Alice")
    user_repository.add_user(user)
    issued_at = datetime(2026, 3, 29, tzinfo=timezone.utc)

    revoke_key = "vk_revoke_1234567890"
    disable_key = "vk_disable_1234567890"
    rotate_key = "vk_rotate_1234567890"
    repository.seed(_record("key-revoke", user.id, revoke_key, encryption, issued_at))
    repository.seed(_record("key-disable", user.id, disable_key, encryption, issued_at))
    repository.seed(_record("key-rotate", user.id, rotate_key, encryption, issued_at))

    dependencies = AppDependencies(
        admin_identity_repository=InMemoryAdminIdentityRepository(
            {"principal:operator": "operator"}
        ),
        virtual_key_admin_service=VirtualKeyLifecycleService(
            repository=repository,
            encryption_service=encryption,
            invalidation_dispatcher=dispatcher,
            clock=lambda: issued_at,
            key_generator=lambda: "vk_rotated_abcdefghijklmnopqrstuvwxyz",
            key_id_generator=lambda: "key-rotated",
        ),
    )
    client = TestClient(create_app(dependencies))
    auth_service = ProxyAuthService(
        virtual_key_repository=repository,
        user_repository=user_repository,
    )

    revoke_response = client.post(
        "/admin/virtual-keys/key-revoke/revoke",
        headers=admin_headers("principal:operator"),
    )
    disable_response = client.post(
        "/admin/virtual-keys/key-disable/disable",
        headers=admin_headers("principal:operator"),
    )
    rotate_response = client.post(
        "/admin/virtual-keys/key-rotate/rotate",
        headers=admin_headers("principal:operator"),
    )

    assert revoke_response.status_code == 200
    assert disable_response.status_code == 200
    assert rotate_response.status_code == 200
    assert repository.get_key("key-revoke").status == VirtualKeyStatus.REVOKED
    assert repository.get_key("key-disable").status == VirtualKeyStatus.DISABLED
    assert repository.get_key("key-rotate").status == VirtualKeyStatus.DISABLED
    assert repository.get_key("key-rotated").status == VirtualKeyStatus.ACTIVE
    assert dispatcher.token_service_invalidations == [user.id, user.id, user.id]
    assert dispatcher.proxy_auth_invalidations == ["key-revoke", "key-disable", "key-rotate"]

    for stale_key in (revoke_key, disable_key, rotate_key):
        with pytest.raises(ServiceError):
            auth_service.authenticate(f"Bearer {stale_key}", request_id="req-admin")


def _record(
    key_id: str,
    user_id: str,
    virtual_key: str,
    encryption: SimpleEnvelopeEncryption,
    issued_at: datetime,
) -> VirtualKeyRecord:
    return VirtualKeyRecord(
        id=key_id,
        user_id=user_id,
        key_hash=hash_virtual_key(virtual_key),
        encrypted_key_blob=encryption.encrypt(virtual_key),
        key_prefix=get_virtual_key_prefix(virtual_key),
        status=VirtualKeyStatus.ACTIVE,
        created_at=issued_at,
    )
