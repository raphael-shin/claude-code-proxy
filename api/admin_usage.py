from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder

from api.admin_auth import require_admin_read
from models.domain import AuditEventRecord, UsageEventRecord

router = APIRouter()


class UsageQueryService(Protocol):
    def query_usage(
        self,
        *,
        user_id: str | None = None,
        team_id: str | None = None,
        model: str | None = None,
    ) -> Sequence[UsageEventRecord]: ...

    def query_audit_events(
        self,
        *,
        user_id: str | None = None,
        team_id: str | None = None,
        model: str | None = None,
        event_type: str | None = None,
    ) -> Sequence[AuditEventRecord]: ...


@router.get("/admin/usage")
def list_usage(
    request: Request,
    user_id: str | None = None,
    team_id: str | None = None,
    model: str | None = None,
) -> dict[str, object]:
    require_admin_read(request)
    items = _usage_query_service(request).query_usage(
        user_id=user_id,
        team_id=team_id,
        model=model,
    )
    return {"items": jsonable_encoder(list(items))}


@router.get("/admin/audit-events")
def list_audit_events(
    request: Request,
    user_id: str | None = None,
    team_id: str | None = None,
    model: str | None = None,
    event_type: str | None = None,
) -> dict[str, object]:
    require_admin_read(request)
    items = _usage_query_service(request).query_audit_events(
        user_id=user_id,
        team_id=team_id,
        model=model,
        event_type=event_type,
    )
    return {"items": jsonable_encoder(list(items))}


def _usage_query_service(request: Request) -> UsageQueryService:
    service = request.app.state.dependencies.usage_query_service
    if service is None:
        raise HTTPException(status_code=500, detail="Usage query service is not configured.")
    return service
