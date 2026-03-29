from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    USER_NOT_REGISTERED = "user_not_registered"
    ACCESS_DENIED = "access_denied"
    AUTHENTICATION_FAILED = "authentication_failed"
    INVALID_IDENTITY = "invalid_identity"
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
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        self.details = details

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
