from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.api_key_helper import (
    ApiKeyHelper,
    ApiKeyHelperError,
    CacheFileHelper,
    ExportedAwsCredentials,
)


class SessionBootstrapperStub:
    def __init__(self) -> None:
        self.ensure_session_calls = 0
        self.export_credentials_calls = 0

    def ensure_session(self) -> None:
        self.ensure_session_calls += 1

    def export_credentials(self) -> ExportedAwsCredentials:
        self.export_credentials_calls += 1
        return ExportedAwsCredentials(
            access_key_id="AKIA123",
            secret_access_key="secret",
            session_token="token",
        )


class TokenServiceClientStub:
    def __init__(self, *, virtual_key: str | None = None, error: Exception | None = None) -> None:
        self.virtual_key = virtual_key
        self.error = error
        self.calls = 0

    def get_or_create_key(self, credentials: ExportedAwsCredentials) -> str:
        del credentials
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.virtual_key is not None
        return self.virtual_key


def test_api_key_helper_returns_cached_key_within_100ms(tmp_path: Path) -> None:
    now = datetime(2026, 3, 29, tzinfo=timezone.utc)
    cache = CacheFileHelper(path=tmp_path / "cache.json")
    cache.store(virtual_key="vk_cached_1234567890", now=now, ttl_seconds=300)
    bootstrapper = SessionBootstrapperStub()
    token_service = TokenServiceClientStub(virtual_key="vk_new_1234567890")
    helper = ApiKeyHelper(
        cache=cache,
        session_bootstrapper=bootstrapper,
        token_service_client=token_service,
        clock=lambda: now,
    )

    started_at = time.perf_counter()
    result = helper.get_api_key()
    elapsed_ms = (time.perf_counter() - started_at) * 1000

    assert result == "vk_cached_1234567890"
    assert elapsed_ms < 100
    assert bootstrapper.ensure_session_calls == 0
    assert bootstrapper.export_credentials_calls == 0
    assert token_service.calls == 0


@pytest.mark.parametrize("seed_corrupt_cache", [False, True])
def test_api_key_helper_refetches_on_cache_miss_or_corruption(
    tmp_path: Path,
    seed_corrupt_cache: bool,
) -> None:
    now = datetime(2026, 3, 29, tzinfo=timezone.utc)
    cache_path = tmp_path / "cache.json"
    if seed_corrupt_cache:
        cache_path.write_text("{not-json")

    cache = CacheFileHelper(path=cache_path)
    bootstrapper = SessionBootstrapperStub()
    token_service = TokenServiceClientStub(virtual_key="vk_refetched_1234567890")
    helper = ApiKeyHelper(
        cache=cache,
        session_bootstrapper=bootstrapper,
        token_service_client=token_service,
        clock=lambda: now,
    )

    result = helper.get_api_key()
    cached = cache.load(now=now)

    assert result == "vk_refetched_1234567890"
    assert bootstrapper.ensure_session_calls == 1
    assert bootstrapper.export_credentials_calls == 1
    assert token_service.calls == 1
    assert cached is not None
    assert cached.virtual_key == "vk_refetched_1234567890"


def test_api_key_helper_fails_fast_on_token_service_connection_error(tmp_path: Path) -> None:
    now = datetime(2026, 3, 29, tzinfo=timezone.utc)
    cache = CacheFileHelper(path=tmp_path / "cache.json")
    bootstrapper = SessionBootstrapperStub()
    token_service = TokenServiceClientStub(
        error=ApiKeyHelperError("Failed to connect to Token Service.")
    )
    helper = ApiKeyHelper(
        cache=cache,
        session_bootstrapper=bootstrapper,
        token_service_client=token_service,
        clock=lambda: now,
    )

    started_at = time.perf_counter()
    with pytest.raises(ApiKeyHelperError, match="Failed to connect to Token Service."):
        helper.get_api_key()
    elapsed_ms = (time.perf_counter() - started_at) * 1000

    assert elapsed_ms < 1000
    assert not (tmp_path / "cache.json").exists()
