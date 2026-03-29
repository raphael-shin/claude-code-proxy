from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Callable, Protocol

from fastapi import APIRouter, HTTPException, Request

from api.admin_auth import require_admin_write
from models.domain import VirtualKeyRecord, VirtualKeyStatus
from security.encryption import EncryptionService
from security.keys import generate_virtual_key, get_virtual_key_prefix, hash_virtual_key

router = APIRouter()

Clock = Callable[[], datetime]
KeyGenerator = Callable[[], str]
KeyIdGenerator = Callable[[], str]


class VirtualKeyAdminRepository(Protocol):
    def get_key(self, key_id: str) -> VirtualKeyRecord | None: ...

    def save_key(self, record: VirtualKeyRecord) -> None: ...


class VirtualKeyInvalidationDispatcher(Protocol):
    def invalidate_token_service_cache(self, user_id: str) -> None: ...

    def invalidate_proxy_auth_cache(self, key_id: str) -> None: ...


class VirtualKeyLifecycleService:
    def __init__(
        self,
        *,
        repository: VirtualKeyAdminRepository,
        encryption_service: EncryptionService,
        invalidation_dispatcher: VirtualKeyInvalidationDispatcher,
        clock: Clock,
        key_generator: KeyGenerator = generate_virtual_key,
        key_id_generator: KeyIdGenerator = generate_virtual_key,
    ) -> None:
        self._repository = repository
        self._encryption_service = encryption_service
        self._invalidation_dispatcher = invalidation_dispatcher
        self._clock = clock
        self._key_generator = key_generator
        self._key_id_generator = key_id_generator

    def revoke(self, key_id: str) -> VirtualKeyRecord:
        record = self._require_key(key_id)
        revoked = replace(
            record,
            status=VirtualKeyStatus.REVOKED,
            revoked_at=self._clock(),
        )
        self._repository.save_key(revoked)
        self._invalidate(revoked)
        return revoked

    def disable(self, key_id: str) -> VirtualKeyRecord:
        record = self._require_key(key_id)
        disabled = replace(record, status=VirtualKeyStatus.DISABLED)
        self._repository.save_key(disabled)
        self._invalidate(disabled)
        return disabled

    def rotate(self, key_id: str) -> tuple[VirtualKeyRecord, VirtualKeyRecord]:
        record = self._require_key(key_id)
        disabled = replace(record, status=VirtualKeyStatus.DISABLED)
        self._repository.save_key(disabled)
        self._invalidate(disabled)

        new_virtual_key = self._key_generator()
        now = self._clock()
        replacement = VirtualKeyRecord(
            id=self._key_id_generator(),
            user_id=record.user_id,
            key_hash=hash_virtual_key(new_virtual_key),
            encrypted_key_blob=self._encryption_service.encrypt(new_virtual_key),
            key_prefix=get_virtual_key_prefix(new_virtual_key),
            status=VirtualKeyStatus.ACTIVE,
            created_at=now,
        )
        self._repository.save_key(replacement)
        return disabled, replacement

    def _require_key(self, key_id: str) -> VirtualKeyRecord:
        record = self._repository.get_key(key_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Virtual key not found.")
        return record

    def _invalidate(self, record: VirtualKeyRecord) -> None:
        self._invalidation_dispatcher.invalidate_token_service_cache(record.user_id)
        self._invalidation_dispatcher.invalidate_proxy_auth_cache(record.id)


@router.post("/admin/virtual-keys/{key_id}/revoke")
def revoke_virtual_key(key_id: str, request: Request) -> dict[str, str]:
    require_admin_write(request)
    record = _virtual_key_service(request).revoke(key_id)
    return {
        "key_id": record.id,
        "user_id": record.user_id,
        "status": record.status.value,
    }


@router.post("/admin/virtual-keys/{key_id}/disable")
def disable_virtual_key(key_id: str, request: Request) -> dict[str, str]:
    require_admin_write(request)
    record = _virtual_key_service(request).disable(key_id)
    return {
        "key_id": record.id,
        "user_id": record.user_id,
        "status": record.status.value,
    }


@router.post("/admin/virtual-keys/{key_id}/rotate")
def rotate_virtual_key(key_id: str, request: Request) -> dict[str, str]:
    require_admin_write(request)
    previous, replacement = _virtual_key_service(request).rotate(key_id)
    return {
        "old_key_id": previous.id,
        "new_key_id": replacement.id,
        "user_id": replacement.user_id,
        "status": replacement.status.value,
    }


def _virtual_key_service(request: Request) -> VirtualKeyLifecycleService:
    service = request.app.state.dependencies.virtual_key_admin_service
    if service is None:
        raise HTTPException(status_code=500, detail="Virtual key admin service is not configured.")
    return service
