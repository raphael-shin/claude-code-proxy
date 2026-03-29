from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import uuid4

from models.domain import TokenIssueResult
from models.errors import ErrorCode, ServiceError, build_error_envelope, user_not_registered_error
from repositories.user_repository import UserRepository
from token_service.identity import IdentityResolutionError, extract_username_from_event


class IssueService(Protocol):
    def get_or_create_key(self, user_id: str, *, request_id: str) -> TokenIssueResult: ...


def default_request_id_generator() -> str:
    return str(uuid4())


@dataclass(slots=True)
class TokenServiceHandlerDependencies:
    user_repository: UserRepository
    issue_service: IssueService
    request_id_generator: Callable[[], str] = default_request_id_generator


def _resolve_request_id(event: dict, request_id_generator: Callable[[], str]) -> str:
    request_context = event.get("requestContext", {})
    request_id = request_context.get("requestId")
    if isinstance(request_id, str) and request_id.strip():
        return request_id
    return request_id_generator()


def _json_response(status_code: int, payload: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def handle_get_or_create_key(
    event: dict,
    context: object | None = None,
    *,
    dependencies: TokenServiceHandlerDependencies,
) -> dict:
    del context
    request_id = _resolve_request_id(event, dependencies.request_id_generator)
    try:
        username = extract_username_from_event(event)
        user_id = dependencies.user_repository.get_user_id_for_username(username)
        if user_id is None:
            raise user_not_registered_error(request_id, details={"username": username})
        result = dependencies.issue_service.get_or_create_key(user_id, request_id=request_id)
        return _json_response(
            200,
            {
                "virtual_key": result.virtual_key,
                "user_id": result.user_id,
                "key_id": result.key_id,
                "key_prefix": result.key_prefix,
                "request_id": request_id,
            },
        )
    except IdentityResolutionError as error:
        return _json_response(
            400,
            build_error_envelope(
                ServiceError(
                    code=ErrorCode.INVALID_IDENTITY,
                    message=str(error),
                    status_code=400,
                    request_id=request_id,
                )
            ),
        )
    except ServiceError as error:
        return _json_response(error.status_code, build_error_envelope(error))
    except Exception:
        return _json_response(
            500,
            build_error_envelope(
                ServiceError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message="Internal server error",
                    status_code=500,
                    request_id=request_id,
                )
            ),
        )

