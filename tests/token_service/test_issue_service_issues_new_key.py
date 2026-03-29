from __future__ import annotations

from datetime import datetime, timezone

from models.domain import TokenIssueSource, UserRecord
from security.keys import hash_virtual_key
from token_service.issue_service import TokenIssueService
from tests.fakes import FakeClock, FakeEncryptionService, InMemoryUserRepository, InMemoryVirtualKeyCacheRepository, InMemoryVirtualKeyLedgerRepository


def test_allowed_user_without_existing_key_gets_new_key_and_cache_entry() -> None:
    clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    user_repository = InMemoryUserRepository()
    user_repository.add_user(UserRecord(id="user-1", email="dev@example.com", display_name="Dev One"))
    ledger = InMemoryVirtualKeyLedgerRepository()
    cache = InMemoryVirtualKeyCacheRepository()
    service = TokenIssueService(
        user_repository=user_repository,
        virtual_key_repository=ledger,
        virtual_key_cache=cache,
        encryption_service=FakeEncryptionService(),
        clock=clock,
        key_generator=lambda: "vk_new_key",
    )

    result = service.get_or_create_key("user-1", request_id="req-1")

    assert result.virtual_key == "vk_new_key"
    assert result.source == TokenIssueSource.ISSUED
    stored_record = ledger.saved_records[0]
    assert stored_record.key_hash == hash_virtual_key("vk_new_key")
    assert stored_record.encrypted_key_blob == "enc::vk_new_key"
    assert "virtual_key" not in stored_record.__dataclass_fields__
    assert cache.saved_entries[0].encrypted_key_ref == stored_record.encrypted_key_blob
    assert cache.saved_entries[0].ttl == int(clock().timestamp()) + 900

