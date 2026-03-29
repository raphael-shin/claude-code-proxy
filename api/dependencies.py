from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Callable

from repositories.user_repository import UserRepository
from repositories.virtual_key_repository import (
    VirtualKeyCacheRepository,
    VirtualKeyLedgerRepository,
)
from security.encryption import EncryptionService
from security.keys import generate_virtual_key
from token_service.handler import (
    TokenServiceHandlerDependencies,
    default_request_id_generator,
)
from token_service.issue_service import DEFAULT_CACHE_TTL, Clock, KeyGenerator, TokenIssueService


@dataclass(slots=True)
class AppDependencies:
    token_service: TokenServiceHandlerDependencies | None = None
    auth_service: Any | None = None
    model_resolver: Any | None = None
    policy_engine: Any | None = None
    quota_engine: Any | None = None
    rate_limiter: Any | None = None
    bedrock_client: Any | None = None
    request_id_generator: Callable[[], str] = default_request_id_generator
    readiness_checks: tuple[Callable[[], bool], ...] = field(default_factory=tuple)


def build_token_service_dependencies(
    *,
    user_repository: UserRepository,
    virtual_key_repository: VirtualKeyLedgerRepository,
    virtual_key_cache: VirtualKeyCacheRepository,
    encryption_service: EncryptionService,
    clock: Clock,
    request_id_generator: Callable[[], str] = default_request_id_generator,
    key_generator: KeyGenerator = generate_virtual_key,
    cache_ttl: timedelta = DEFAULT_CACHE_TTL,
) -> TokenServiceHandlerDependencies:
    issue_service = TokenIssueService(
        user_repository=user_repository,
        virtual_key_repository=virtual_key_repository,
        virtual_key_cache=virtual_key_cache,
        encryption_service=encryption_service,
        clock=clock,
        key_generator=key_generator,
        cache_ttl=cache_ttl,
    )
    return TokenServiceHandlerDependencies(
        user_repository=user_repository,
        issue_service=issue_service,
        request_id_generator=request_id_generator,
    )
