from __future__ import annotations

from typing import Any, Mapping

from fastapi.responses import JSONResponse

from models.errors import ErrorCode, ServiceError

ANTHROPIC_AUTHENTICATION_ERROR = "authentication_error"
ANTHROPIC_PERMISSION_ERROR = "permission_error"
ANTHROPIC_INVALID_REQUEST_ERROR = "invalid_request_error"
ANTHROPIC_RATE_LIMIT_ERROR = "rate_limit_error"
ANTHROPIC_API_ERROR = "api_error"


def anthropic_error_response(
    *,
    status_code: int,
    error_type: str,
    message: str,
    request_id: str,
    headers: Mapping[str, str] | None = None,
    details: Mapping[str, Any] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "type": "error",
        "error": {
            "type": error_type,
            "message": message,
        },
        "request_id": request_id,
    }
    if details:
        payload["error"]["details"] = dict(details)
    return JSONResponse(status_code=status_code, content=payload, headers=dict(headers or {}))


def service_error_response(error: ServiceError) -> JSONResponse:
    if error.code == ErrorCode.AUTHENTICATION_FAILED:
        error_type = ANTHROPIC_AUTHENTICATION_ERROR
    elif error.code == ErrorCode.ACCESS_DENIED:
        error_type = ANTHROPIC_PERMISSION_ERROR
    elif error.code == ErrorCode.INTERNAL_ERROR:
        error_type = ANTHROPIC_API_ERROR
    else:
        error_type = ANTHROPIC_INVALID_REQUEST_ERROR
    return anthropic_error_response(
        status_code=error.status_code,
        error_type=error_type,
        message=error.message,
        request_id=error.request_id,
        details=error.details,
    )
