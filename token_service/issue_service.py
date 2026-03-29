from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Callable
from uuid import uuid4

from models.domain import TokenIssueResult, TokenIssueSource, UserRecord, VirtualKeyCacheEntry, VirtualKeyRecord, VirtualKeyStatus
from models.errors import ErrorCode, ServiceError, user_not_registered_error
from repositories.user_repository import UserRepository
from repositories.virtual_key_repository import VirtualKeyCacheRepository, VirtualKeyLedgerRepository
from security.encryption import EncryptionService
from security.keys import generate_virtual_key, get_virtual_key_prefix, hash_virtual_key

DEFAULT_CACHE_TTL = timedelta(minutes=15)
MAX_CACHE_TTL = timedelta(hours=1)


class IssueDenialReason(str, Enum):
    USER_NOT_REGISTERED = "user_not_registered"
    ACCESS_DENIED = "access_denied"


Clock = Callable[[], datetime]
KeyGenerator = Callable[[], str]


def _normalize_cache_ttl(cache_ttl: timedelta) -> timedelta:
    if cache_ttl <= timedelta(0):
        return DEFAULT_CACHE_TTL
    return min(cache_ttl, MAX_CACHE_TTL)


class TokenIssueService:
    def __init__(
        self,
        *,
        user_repository: UserRepository,
        virtual_key_repository: VirtualKeyLedgerRepository,
        virtual_key_cache: VirtualKeyCacheRepository,
        encryption_service: EncryptionService,
        clock: Clock,
        key_generator: KeyGenerator = generate_virtual_key,
        cache_ttl: timedelta = DEFAULT_CACHE_TTL,
    ) -> None:
        self._user_repository = user_repository
        self._virtual_key_repository = virtual_key_repository
        self._virtual_key_cache = virtual_key_cache
        self._encryption_service = encryption_service
        self._clock = clock
        self._key_generator = key_generator
        self._cache_ttl = _normalize_cache_ttl(cache_ttl)

    def get_or_create_key(self, user_id: str, *, request_id: str) -> TokenIssueResult:
        now = self._clock()
        cached_entry = self._virtual_key_cache.get_active_key(user_id, now)
        if cached_entry is not None:
            return TokenIssueResult(
                virtual_key=self._encryption_service.decrypt(cached_entry.encrypted_key_ref),
                user_id=user_id,
                key_id=cached_entry.virtual_key_id,
                key_prefix=cached_entry.key_prefix,
                status=cached_entry.status,
                source=TokenIssueSource.CACHE,
            )

        user = self._require_allowed_user(user_id, request_id=request_id)
        existing_key = self._virtual_key_repository.get_active_key_for_user(user.id)
        if existing_key is not None:
            self._cache_key_record(existing_key, now=now)
            return TokenIssueResult(
                virtual_key=self._encryption_service.decrypt(existing_key.encrypted_key_blob),
                user_id=user.id,
                key_id=existing_key.id,
                key_prefix=existing_key.key_prefix,
                status=existing_key.status,
                source=TokenIssueSource.REUSED,
                expires_at=existing_key.expires_at,
            )

        return self._issue_new_key(user, now=now)

    def _require_allowed_user(self, user_id: str, *, request_id: str) -> UserRecord:
        user = self._user_repository.get_user(user_id)
        if user is None:
            raise user_not_registered_error(request_id)
        if not user.proxy_access_enabled or not user.is_active:
            raise ServiceError(
                code=ErrorCode.ACCESS_DENIED,
                message="Proxy access is disabled for this user.",
                status_code=403,
                request_id=request_id,
            )
        return user

    def _issue_new_key(self, user: UserRecord, *, now: datetime) -> TokenIssueResult:
        virtual_key = self._key_generator()
        encrypted_key = self._encryption_service.encrypt(virtual_key)
        record = VirtualKeyRecord(
            id=str(uuid4()),
            user_id=user.id,
            key_hash=hash_virtual_key(virtual_key),
            encrypted_key_blob=encrypted_key,
            key_prefix=get_virtual_key_prefix(virtual_key),
            status=VirtualKeyStatus.ACTIVE,
            created_at=now,
        )
        self._virtual_key_repository.save_key(record)
        self._cache_key_record(record, now=now)
        return TokenIssueResult(
            virtual_key=virtual_key,
            user_id=user.id,
            key_id=record.id,
            key_prefix=record.key_prefix,
            status=record.status,
            source=TokenIssueSource.ISSUED,
        )

    def _cache_key_record(self, record: VirtualKeyRecord, *, now: datetime) -> None:
        expires_at = int((now + self._cache_ttl).timestamp())
        self._virtual_key_cache.put_active_key(
            VirtualKeyCacheEntry(
                user_id=record.user_id,
                virtual_key_id=record.id,
                encrypted_key_ref=record.encrypted_key_blob,
                key_prefix=record.key_prefix,
                status=record.status,
                ttl=expires_at,
            )
        )

