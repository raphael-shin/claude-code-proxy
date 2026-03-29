from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Mapping, Protocol
from uuid import uuid4

from models.domain import TokenIssueResult
from models.errors import (
    ErrorCode,
    ServiceError,
    build_error_envelope,
    internal_error,
    user_not_registered_error,
)
from repositories.user_repository import UserRepository
from token_service.identity import IdentityResolutionError, extract_username_from_event

TOKEN_SERVICE_REQUEST_COUNT_METRIC = "token_service.requests"
TOKEN_SERVICE_ERROR_COUNT_METRIC = "token_service.errors"
TOKEN_SERVICE_LATENCY_METRIC = "token_service.request_latency_ms"
TOKEN_SERVICE_CACHE_HIT_METRIC = "token_service.cache_hits"
TOKEN_SERVICE_CACHE_MISS_METRIC = "token_service.cache_misses"
TOKEN_SERVICE_FAILURE_EVENT = "token_service_request_failed"
TOKEN_SERVICE_LOGGER_NAME = "claude_code_proxy.token_service"

logger = logging.getLogger(TOKEN_SERVICE_LOGGER_NAME)


class IssueService(Protocol):
    def get_or_create_key(self, user_id: str, *, request_id: str) -> TokenIssueResult: ...


class TokenServiceMetricsRecorder(Protocol):
    def increment(
        self,
        name: str,
        *,
        value: int = 1,
        tags: Mapping[str, str] | None = None,
    ) -> None: ...

    def observe(
        self,
        name: str,
        value: float,
        *,
        tags: Mapping[str, str] | None = None,
    ) -> None: ...


def default_request_id_generator() -> str:
    return str(uuid4())


@dataclass(slots=True)
class TokenServiceHandlerDependencies:
    user_repository: UserRepository
    issue_service: IssueService
    request_id_generator: Callable[[], str] = default_request_id_generator
    metrics: TokenServiceMetricsRecorder | None = None


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
    started_at = perf_counter()
    response: dict
    token_source: str | None = None
    try:
        username = extract_username_from_event(event)
        user_id = dependencies.user_repository.get_user_id_for_username(username)
        if user_id is None:
            raise user_not_registered_error(request_id, details={"username": username})
        result = dependencies.issue_service.get_or_create_key(user_id, request_id=request_id)
        token_source = result.source.value
        response = _json_response(
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
        response = _json_response(
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
        response = _json_response(error.status_code, build_error_envelope(error))
    except Exception:
        response = _json_response(
            500,
            build_error_envelope(
                internal_error(
                    request_id,
                )
            ),
        )
    latency_ms = int((perf_counter() - started_at) * 1000)
    _record_metrics(
        dependencies,
        status_code=response["statusCode"],
        latency_ms=latency_ms,
        token_source=token_source,
    )
    if response["statusCode"] >= 400:
        error_type = json.loads(response["body"]).get("error", {}).get("type")
        logger.warning(
            json.dumps(
                {
                    "event": TOKEN_SERVICE_FAILURE_EVENT,
                    "request_id": request_id,
                    "status_code": response["statusCode"],
                    "error_type": error_type,
                },
                sort_keys=True,
            )
        )
    return response


def _record_metrics(
    dependencies: TokenServiceHandlerDependencies,
    *,
    status_code: int,
    latency_ms: int,
    token_source: str | None,
) -> None:
    recorder = dependencies.metrics
    if recorder is None:
        return

    tags = {
        "operation": "get_or_create_key",
        "status_code": str(status_code),
    }
    recorder.increment(TOKEN_SERVICE_REQUEST_COUNT_METRIC, tags=tags)
    recorder.observe(TOKEN_SERVICE_LATENCY_METRIC, float(latency_ms), tags=tags)
    if status_code >= 400:
        recorder.increment(TOKEN_SERVICE_ERROR_COUNT_METRIC, tags=tags)
    if token_source == "cache":
        recorder.increment(TOKEN_SERVICE_CACHE_HIT_METRIC, tags={"operation": "get_or_create_key"})
    elif token_source is not None:
        recorder.increment(TOKEN_SERVICE_CACHE_MISS_METRIC, tags={"operation": "get_or_create_key"})
