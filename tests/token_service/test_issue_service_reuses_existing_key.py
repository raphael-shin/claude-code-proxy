from __future__ import annotations

from datetime import datetime, timezone

from models.domain import TokenIssueSource, UserRecord, VirtualKeyRecord, VirtualKeyStatus
from token_service.issue_service import TokenIssueService
from tests.fakes import FakeClock, FakeEncryptionService, InMemoryUserRepository, InMemoryVirtualKeyCacheRepository, InMemoryVirtualKeyLedgerRepository


def test_existing_active_key_is_reused_and_cache_is_refreshed() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    user_repository = InMemoryUserRepository()
    user_repository.add_user(UserRecord(id="user-1", email="dev@example.com", display_name="Dev One"))
    ledger = InMemoryVirtualKeyLedgerRepository()
    ledger.seed(
        VirtualKeyRecord(
            id="key-1",
            user_id="user-1",
            key_hash="hash-1",
            encrypted_key_blob="enc::vk_existing",
            key_prefix="vk_existing",
            status=VirtualKeyStatus.ACTIVE,
            created_at=clock(),
        )
    )
    cache = InMemoryVirtualKeyCacheRepository()
    service = TokenIssueService(
        user_repository=user_repository,
        virtual_key_repository=ledger,
        virtual_key_cache=cache,
        encryption_service=FakeEncryptionService(),
        clock=clock,
    )

    result = service.get_or_create_key("user-1", request_id="req-1")

    assert result.virtual_key == "vk_existing"
    assert result.source == TokenIssueSource.REUSED
    assert cache.saved_entries[0].encrypted_key_ref == "enc::vk_existing"

