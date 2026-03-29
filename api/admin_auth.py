from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request

ADMIN_ROLE_OPERATOR = "operator"
ADMIN_ROLE_AUDITOR = "auditor"


@dataclass(frozen=True, slots=True)
class AdminActor:
    principal_id: str
    role: str


def require_admin_read(request: Request) -> AdminActor:
    return _require_admin_role(request, allowed_roles=_allowed_roles_for_read())


def require_admin_write(request: Request) -> AdminActor:
    return _require_admin_role(request, allowed_roles=(ADMIN_ROLE_OPERATOR,))


def _allowed_roles_for_read() -> tuple[str, ...]:
    return (ADMIN_ROLE_OPERATOR, ADMIN_ROLE_AUDITOR)


def _require_admin_role(request: Request, *, allowed_roles: tuple[str, ...]) -> AdminActor:
    dependencies = request.app.state.dependencies
    repository = getattr(dependencies, "admin_identity_repository", None)
    principal_header = getattr(dependencies, "admin_principal_header", "X-Admin-Principal")
    principal_id = request.headers.get(principal_header)

    if repository is None or principal_id is None or not principal_id.strip():
        raise HTTPException(status_code=403, detail="Admin access denied.")

    role = repository.get_admin_role(principal_id.strip())
    if role is None or role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Admin access denied.")

    return AdminActor(principal_id=principal_id.strip(), role=role)
