from __future__ import annotations

from models.context import AuthenticatedRequestContext, RequestContext, UserContext
from models.domain import UserRecord


def restore_trusted_request_context(
    *,
    request_id: str,
    user: UserRecord,
    virtual_key_id: str,
    key_hash: str,
    key_prefix: str,
) -> AuthenticatedRequestContext:
    return AuthenticatedRequestContext(
        request=RequestContext(
            request_id=request_id,
            user=UserContext(
                user_id=user.id,
                email=user.email,
                groups=user.groups,
                department=user.department,
            ),
        ),
        user_record=user,
        virtual_key_id=virtual_key_id,
        key_hash=key_hash,
        key_prefix=key_prefix,
    )
