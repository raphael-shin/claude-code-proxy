from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    USER_NOT_REGISTERED = "user_not_registered"
    ACCESS_DENIED = "access_denied"
    AUTHENTICATION_FAILED = "authentication_failed"
    INVALID_IDENTITY = "invalid_identity"
    INVALID_REQUEST = "invalid_request"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    UPSTREAM_FAILURE = "upstream_failure"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True, slots=True)
class ErrorInfo:
    type: ErrorCode
    message: str
    request_id: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.type.value,
            "message": self.message,
            "request_id": self.request_id,
        }
        if self.details:
            payload["details"] = self.details
        return payload


@dataclass(frozen=True, slots=True)
class ErrorEnvelope:
    error: ErrorInfo

    def to_dict(self) -> dict[str, Any]:
        return {"error": self.error.to_dict()}


class ServiceError(Exception):
    def __init__(
        self,
        *,
        code: ErrorCode,
        message: str,
        status_code: int,
        request_id: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        self.details = details
        self.headers = headers

    def to_envelope(self) -> ErrorEnvelope:
        return ErrorEnvelope(
            ErrorInfo(
                type=self.code,
                message=self.message,
                request_id=self.request_id,
                details=self.details,
            )
        )


def build_error_envelope(error: ServiceError) -> dict[str, Any]:
    return error.to_envelope().to_dict()


def user_not_registered_error(
    request_id: str,
    *,
    details: dict[str, Any] | None = None,
) -> ServiceError:
    return ServiceError(
        code=ErrorCode.USER_NOT_REGISTERED,
        message="The caller is not provisioned for Claude Code Proxy.",
        status_code=403,
        request_id=request_id,
        details=details,
    )


def authentication_failed_error(
    request_id: str,
    *,
    details: dict[str, Any] | None = None,
    message: str = "Authentication failed.",
) -> ServiceError:
    return ServiceError(
        code=ErrorCode.AUTHENTICATION_FAILED,
        message=message,
        status_code=401,
        request_id=request_id,
        details=details,
    )


def access_denied_error(
    request_id: str,
    *,
    details: dict[str, Any] | None = None,
    message: str = "Access denied.",
) -> ServiceError:
    return ServiceError(
        code=ErrorCode.ACCESS_DENIED,
        message=message,
        status_code=403,
        request_id=request_id,
        details=details,
    )


def invalid_request_error(
    request_id: str,
    *,
    message: str,
    details: dict[str, Any] | None = None,
) -> ServiceError:
    return ServiceError(
        code=ErrorCode.INVALID_REQUEST,
        message=message,
        status_code=400,
        request_id=request_id,
        details=details,
    )


def rate_limit_exceeded_error(
    request_id: str,
    *,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    message: str = "Rate limit exceeded.",
) -> ServiceError:
    return ServiceError(
        code=ErrorCode.RATE_LIMIT_EXCEEDED,
        message=message,
        status_code=429,
        request_id=request_id,
        details=details,
        headers=headers,
    )


def upstream_failure_error(
    request_id: str,
    *,
    details: dict[str, Any] | None = None,
    message: str = "Upstream request failed.",
    status_code: int = 502,
) -> ServiceError:
    return ServiceError(
        code=ErrorCode.UPSTREAM_FAILURE,
        message=message,
        status_code=status_code,
        request_id=request_id,
        details=details,
    )


def internal_error(
    request_id: str,
    *,
    details: dict[str, Any] | None = None,
    message: str = "Internal server error",
    status_code: int = 500,
) -> ServiceError:
    return ServiceError(
        code=ErrorCode.INTERNAL_ERROR,
        message=message,
        status_code=status_code,
        request_id=request_id,
        details=details,
    )
