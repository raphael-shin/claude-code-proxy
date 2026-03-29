from __future__ import annotations

from typing import Any, Mapping

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api.errors import (
    ANTHROPIC_API_ERROR,
    ANTHROPIC_INVALID_REQUEST_ERROR,
    ANTHROPIC_PERMISSION_ERROR,
    ANTHROPIC_RATE_LIMIT_ERROR,
    anthropic_error_response,
    service_error_response,
)
from proxy.bedrock_converse.request_builder import BedrockRequestBuildError, build_converse_request
from proxy.bedrock_converse.response_parser import parse_converse_response
from proxy.model_resolver import ModelResolutionError

router = APIRouter()


@router.post("/v1/messages")
async def create_message(request: Request) -> JSONResponse:
    body = await request.json()
    dependencies = request.app.state.dependencies
    request_id = dependencies.request_id_generator()

    try:
        authenticated = dependencies.auth_service.authenticate(
            request.headers.get("Authorization"),
            request_id=request_id,
            headers=dict(request.headers),
            body=body,
        )
    except Exception as error:
        return _error_to_response(error, request_id=request_id)

    try:
        resolved_model = dependencies.model_resolver.resolve(body["model"])
        policy_decision = dependencies.policy_engine.evaluate(
            user=authenticated.user_record,
            model=body["model"],
            policies=(),
        )
        if not policy_decision.allowed:
            return anthropic_error_response(
                status_code=403,
                error_type=ANTHROPIC_PERMISSION_ERROR,
                message=f"Request blocked by policy: {policy_decision.denial_reason}.",
                request_id=request_id,
            )

        quota_decision = dependencies.quota_engine.evaluate(
            budget_policies=(),
            current_usage=0.0,
            requested_usage=None,
            model_id=resolved_model.bedrock_model_id,
            token_usage=None,
        )
        if not quota_decision.allowed:
            return anthropic_error_response(
                status_code=403,
                error_type=ANTHROPIC_PERMISSION_ERROR,
                message=f"Request blocked by quota: {quota_decision.denial_reason}.",
                request_id=request_id,
            )

        rate_limit_decision = dependencies.rate_limiter.check(authenticated.user.user_id)
        if not rate_limit_decision.allowed:
            headers = {}
            if rate_limit_decision.retry_after_seconds is not None:
                headers["Retry-After"] = str(rate_limit_decision.retry_after_seconds)
            return anthropic_error_response(
                status_code=429,
                error_type=ANTHROPIC_RATE_LIMIT_ERROR,
                message="Rate limit exceeded.",
                request_id=request_id,
                headers=headers,
            )

        converse_request = build_converse_request(body, resolved_model=resolved_model)
        raw_response = dependencies.bedrock_client.converse(converse_request)
        parsed_response = parse_converse_response(raw_response, model=body["model"])
        return JSONResponse(status_code=200, content=parsed_response)
    except Exception as error:
        return _error_to_response(error, request_id=request_id)


@router.post("/v1/messages/count_tokens")
async def count_tokens(request: Request) -> JSONResponse:
    body = await request.json()
    dependencies = request.app.state.dependencies
    request_id = dependencies.request_id_generator()

    try:
        dependencies.auth_service.authenticate(
            request.headers.get("Authorization"),
            request_id=request_id,
            headers=dict(request.headers),
            body=body,
        )
        resolved_model = dependencies.model_resolver.resolve(body["model"])
        converse_request = build_converse_request(body, resolved_model=resolved_model)
        count_response = dependencies.bedrock_client.count_tokens(converse_request)
    except Exception as error:
        return _error_to_response(error, request_id=request_id)

    input_tokens = int(
        count_response.get("inputTokens", count_response.get("input_tokens", 0)) or 0
    )
    return JSONResponse(status_code=200, content={"input_tokens": input_tokens})


def _error_to_response(error: Exception, *, request_id: str) -> JSONResponse:
    if isinstance(error, BedrockRequestBuildError):
        return anthropic_error_response(
            status_code=400,
            error_type=ANTHROPIC_INVALID_REQUEST_ERROR,
            message=error.message,
            request_id=request_id,
            details={"reason": error.reason},
        )
    if isinstance(error, ModelResolutionError):
        return anthropic_error_response(
            status_code=400,
            error_type=ANTHROPIC_INVALID_REQUEST_ERROR,
            message=error.message,
            request_id=request_id,
            details={"reason": error.reason},
        )
    if hasattr(error, "status_code") and hasattr(error, "code"):
        return service_error_response(error)  # type: ignore[arg-type]
    return anthropic_error_response(
        status_code=502,
        error_type=ANTHROPIC_API_ERROR,
        message="Upstream request failed.",
        request_id=request_id,
        details={"reason": error.__class__.__name__},
    )
