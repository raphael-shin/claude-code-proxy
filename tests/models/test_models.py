from __future__ import annotations

from models.context import RequestContext, UserContext
from models.errors import ErrorCode, ErrorEnvelope, ErrorInfo


def test_request_context_keeps_user_context() -> None:
    context = RequestContext(
        request_id="req-1",
        user=UserContext(user_id="user-1", email="dev@example.com", groups=["eng"], department="platform"),
    )

    assert context.user is not None
    assert context.user.groups == ("eng",)


def test_error_envelope_serializes_to_dict() -> None:
    envelope = ErrorEnvelope(
        error=ErrorInfo(
            type=ErrorCode.USER_NOT_REGISTERED,
            message="not provisioned",
            request_id="req-1",
            details={"username": "alice"},
        )
    )

    assert envelope.to_dict() == {
        "error": {
            "type": "user_not_registered",
            "message": "not provisioned",
            "request_id": "req-1",
            "details": {"username": "alice"},
        }
    }

