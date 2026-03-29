from __future__ import annotations

from models.domain import TokenIssueSource, VirtualKeyCacheEntry, VirtualKeyStatus
from token_service.issue_service import TokenIssueService
from tests.fakes import FakeClock, FakeEncryptionService, InMemoryUserRepository, InMemoryVirtualKeyCacheRepository, InMemoryVirtualKeyLedgerRepository


def test_cache_hit_returns_existing_key_without_postgres_lookup() -> None:
    clock = FakeClock()
    cache = InMemoryVirtualKeyCacheRepository()
    cache.seed(
        VirtualKeyCacheEntry(
            user_id="user-1",
            virtual_key_id="key-1",
            encrypted_key_ref="enc::vk_cached",
            key_prefix="vk_cached",
            status=VirtualKeyStatus.ACTIVE,
            ttl=int(clock().timestamp()) + 900,
        )
    )
    user_repository = InMemoryUserRepository()
    ledger = InMemoryVirtualKeyLedgerRepository()
    service = TokenIssueService(
        user_repository=user_repository,
        virtual_key_repository=ledger,
        virtual_key_cache=cache,
        encryption_service=FakeEncryptionService(),
        clock=clock,
    )

    result = service.get_or_create_key("user-1", request_id="req-1")

    assert result.virtual_key == "vk_cached"
    assert result.source == TokenIssueSource.CACHE
    assert user_repository.get_user_calls == []
    assert ledger.get_active_key_calls == []

