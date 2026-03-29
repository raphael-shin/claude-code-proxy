from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from repositories.virtual_key_repository import VirtualKeyCacheRepository

router = APIRouter()


class InternalCacheInvalidateRequest(BaseModel):
    user_id: str


class InternalCacheOpsService(Protocol):
    def invalidate_user_cache(self, user_id: str) -> None: ...


class CacheInvalidationService:
    def __init__(self, *, virtual_key_cache: VirtualKeyCacheRepository) -> None:
        self._virtual_key_cache = virtual_key_cache

    def invalidate_user_cache(self, user_id: str) -> None:
        self._virtual_key_cache.invalidate_user(user_id)


@router.post("/internal/cache/invalidate", status_code=202)
def invalidate_user_cache(
    request: Request,
    payload: InternalCacheInvalidateRequest,
) -> dict[str, str]:
    _require_internal_token(request)
    _internal_cache_ops_service(request).invalidate_user_cache(payload.user_id)
    return {"status": "accepted", "user_id": payload.user_id}


def _require_internal_token(request: Request) -> None:
    expected_token = request.app.state.dependencies.internal_ops_token
    if expected_token is None:
        raise HTTPException(status_code=500, detail="Internal operations token is not configured.")
    provided_token = request.headers.get("X-Internal-Token")
    if provided_token != expected_token:
        raise HTTPException(status_code=403, detail="Internal access denied.")


def _internal_cache_ops_service(request: Request) -> InternalCacheOpsService:
    service = request.app.state.dependencies.internal_cache_ops_service
    if service is None:
        raise HTTPException(
            status_code=500,
            detail="Internal cache operations service is not configured.",
        )
    return service
