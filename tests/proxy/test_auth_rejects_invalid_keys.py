from __future__ import annotations

from datetime import datetime, timezone

import pytest

from models.domain import UserRecord, VirtualKeyRecord, VirtualKeyStatus
from models.errors import ErrorCode, ServiceError
from proxy.auth import (
    AUTH_REASON_INACTIVE_KEY,
    AUTH_REASON_MALFORMED_BEARER,
    AUTH_REASON_MISSING_BEARER,
    AUTH_REASON_UNKNOWN_KEY,
    ProxyAuthService,
)
from security.keys import hash_virtual_key
from tests.fakes import InMemoryUserRepository, InMemoryVirtualKeyLedgerRepository


@pytest.mark.parametrize(
    ("authorization_header", "seed_record", "expected_reason", "expected_lookup_count"),
    [
        (None, None, AUTH_REASON_MISSING_BEARER, 0),
        ("", None, AUTH_REASON_MISSING_BEARER, 0),
        ("Basic vk_example", None, AUTH_REASON_MALFORMED_BEARER, 0),
        ("Bearer", None, AUTH_REASON_MALFORMED_BEARER, 0),
        ("Bearer not-a-virtual-key", None, AUTH_REASON_MALFORMED_BEARER, 0),
        ("Bearer vk_unknown", None, AUTH_REASON_UNKNOWN_KEY, 1),
        (
            "Bearer vk_revoked",
            VirtualKeyRecord(
                id="vk-record-revoked",
                user_id="user-1",
                key_hash=hash_virtual_key("vk_revoked"),
                encrypted_key_blob="encrypted:vk_revoked",
                key_prefix="vk_revoke",
                status=VirtualKeyStatus.REVOKED,
                created_at=datetime(2026, 3, 29, tzinfo=timezone.utc),
            ),
            AUTH_REASON_INACTIVE_KEY,
            1,
        ),
        (
            "Bearer vk_disabled",
            VirtualKeyRecord(
                id="vk-record-disabled",
                user_id="user-1",
                key_hash=hash_virtual_key("vk_disabled"),
                encrypted_key_blob="encrypted:vk_disabled",
                key_prefix="vk_disabl",
                status=VirtualKeyStatus.DISABLED,
                created_at=datetime(2026, 3, 29, tzinfo=timezone.utc),
            ),
            AUTH_REASON_INACTIVE_KEY,
            1,
        ),
    ],
)
def test_auth_rejects_invalid_virtual_keys_before_downstream_work(
    authorization_header: str | None,
    seed_record: VirtualKeyRecord | None,
    expected_reason: str,
    expected_lookup_count: int,
) -> None:
    user_repository = InMemoryUserRepository()
    user_repository.add_user(
        UserRecord(
            id="user-1",
            email="dev@example.com",
            display_name="Dev User",
        )
    )
    virtual_key_repository = InMemoryVirtualKeyLedgerRepository()
    if seed_record is not None:
        virtual_key_repository.seed(seed_record)
    auth_service = ProxyAuthService(
        virtual_key_repository=virtual_key_repository,
        user_repository=user_repository,
    )

    with pytest.raises(ServiceError) as error_info:
        auth_service.authenticate(authorization_header, request_id="req-auth-1")

    error = error_info.value
    assert error.code == ErrorCode.AUTHENTICATION_FAILED
    assert error.status_code == 401
    assert error.details == {"reason": expected_reason}
    assert len(virtual_key_repository.get_key_by_hash_calls) == expected_lookup_count
    assert user_repository.get_user_calls == []
