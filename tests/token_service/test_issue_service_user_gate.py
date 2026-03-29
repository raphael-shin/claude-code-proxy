from __future__ import annotations

import pytest

from models.domain import UserRecord
from models.errors import ErrorCode, ServiceError
from token_service.issue_service import TokenIssueService
from tests.fakes import FakeClock, FakeEncryptionService, InMemoryUserRepository, InMemoryVirtualKeyCacheRepository, InMemoryVirtualKeyLedgerRepository


def test_missing_user_row_returns_403_without_creating_key() -> None:
    ledger = InMemoryVirtualKeyLedgerRepository()
    service = TokenIssueService(
        user_repository=InMemoryUserRepository(),
        virtual_key_repository=ledger,
        virtual_key_cache=InMemoryVirtualKeyCacheRepository(),
        encryption_service=FakeEncryptionService(),
        clock=FakeClock(),
    )

    with pytest.raises(ServiceError) as error_info:
        service.get_or_create_key("missing-user", request_id="req-1")

    assert error_info.value.code == ErrorCode.USER_NOT_REGISTERED
    assert ledger.saved_records == []


def test_access_disabled_user_returns_403_without_creating_key() -> None:
    user_repository = InMemoryUserRepository()
    user_repository.add_user(
        UserRecord(
            id="user-1",
            email="dev@example.com",
            display_name="Dev One",
            proxy_access_enabled=False,
        )
    )
    ledger = InMemoryVirtualKeyLedgerRepository()
    service = TokenIssueService(
        user_repository=user_repository,
        virtual_key_repository=ledger,
        virtual_key_cache=InMemoryVirtualKeyCacheRepository(),
        encryption_service=FakeEncryptionService(),
        clock=FakeClock(),
    )

    with pytest.raises(ServiceError) as error_info:
        service.get_or_create_key("user-1", request_id="req-2")

    assert error_info.value.code == ErrorCode.ACCESS_DENIED
    assert ledger.saved_records == []

