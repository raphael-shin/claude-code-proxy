from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.admin_auth import require_admin_write
from models.domain import IdentityMapping, UserRecord

router = APIRouter()


class UserProvisioningRequest(BaseModel):
    username: str
    user_id: str
    email: str
    display_name: str
    department: str | None = None
    cost_center: str | None = None
    groups: list[str] = Field(default_factory=list)
    proxy_access_enabled: bool = True
    is_active: bool = True


class UserProvisioningStore(Protocol):
    def provision_user(self, *, user: UserRecord, mapping: IdentityMapping) -> None: ...


class UserProvisioningService:
    def __init__(self, *, store: UserProvisioningStore) -> None:
        self._store = store

    def provision(self, request: UserProvisioningRequest) -> tuple[UserRecord, IdentityMapping]:
        user = UserRecord(
            id=request.user_id,
            email=request.email,
            display_name=request.display_name,
            department=request.department,
            cost_center=request.cost_center,
            groups=tuple(request.groups),
            proxy_access_enabled=request.proxy_access_enabled,
            is_active=request.is_active,
        )
        mapping = IdentityMapping(
            username=request.username,
            user_id=request.user_id,
        )
        self._store.provision_user(user=user, mapping=mapping)
        return user, mapping


@router.post("/admin/users", status_code=201)
def create_user(request: Request, payload: UserProvisioningRequest) -> dict[str, object]:
    require_admin_write(request)
    service = _user_provisioning_service(request)
    user, mapping = service.provision(payload)
    return {
        "user_id": user.id,
        "username": mapping.username,
        "email": user.email,
        "display_name": user.display_name,
        "proxy_access_enabled": user.proxy_access_enabled,
        "is_active": user.is_active,
    }


def _user_provisioning_service(request: Request) -> UserProvisioningService:
    service = request.app.state.dependencies.user_provisioning_service
    if service is None:
        raise HTTPException(status_code=500, detail="User provisioning service is not configured.")
    return service
