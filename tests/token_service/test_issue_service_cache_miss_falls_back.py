from __future__ import annotations

from models.domain import TokenIssueSource, UserRecord
from token_service.issue_service import TokenIssueService
from tests.fakes import FakeClock, FakeEncryptionService, InMemoryUserRepository, InMemoryVirtualKeyCacheRepository, InMemoryVirtualKeyLedgerRepository


def test_cache_miss_forces_user_lookup_before_issueing_key() -> None:
    clock = FakeClock()
    user_repository = InMemoryUserRepository()
    user_repository.add_user(
        UserRecord(id="user-1", email="dev@example.com", display_name="Dev One"),
        username="alice",
    )
    ledger = InMemoryVirtualKeyLedgerRepository()
    cache = InMemoryVirtualKeyCacheRepository()
    service = TokenIssueService(
        user_repository=user_repository,
        virtual_key_repository=ledger,
        virtual_key_cache=cache,
        encryption_service=FakeEncryptionService(),
        clock=clock,
        key_generator=lambda: "vk_generated",
    )

    result = service.get_or_create_key("user-1", request_id="req-1")

    assert result.source == TokenIssueSource.ISSUED
    assert user_repository.get_user_calls == ["user-1"]
    assert ledger.get_active_key_calls == ["user-1"]

