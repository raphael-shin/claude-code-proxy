from __future__ import annotations

from time import perf_counter

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from api.errors import (
    error_response_for_exception,
)
from api.observability import resolve_request_id
from models.errors import access_denied_error, rate_limit_exceeded_error
from proxy.audit_logger import DENIAL_REASON_AUTHENTICATION_FAILED, DENIAL_REASON_RATE_LIMITED
from proxy.quota_engine import DENIAL_QUOTA_HARD_LIMIT_EXCEEDED
from proxy.bedrock_converse.request_builder import build_converse_request
from proxy.bedrock_converse.response_parser import parse_converse_response
from proxy.bedrock_converse.stream_decoder import ConverseStreamDecoder

router = APIRouter()


@router.post("/v1/messages")
async def create_message(request: Request) -> JSONResponse:
    body = await request.json()
    dependencies = request.app.state.dependencies
    request_id = resolve_request_id(request)
    started_at = perf_counter()
    audit_logger = dependencies.audit_logger

    try:
        authenticated = dependencies.auth_service.authenticate(
            request.headers.get("Authorization"),
            request_id=request_id,
        )
    except Exception as error:
        if audit_logger is not None:
            audit_logger.record_denial(
                request_id=request_id,
                denial_reason=DENIAL_REASON_AUTHENTICATION_FAILED,
                requested_model=body.get("model"),
            )
        return error_response_for_exception(error, request_id=request_id)

    try:
        resolved_model = dependencies.model_resolver.resolve(body["model"])
        policy_decision = dependencies.policy_engine.evaluate(
            user=authenticated.user_record,
            model=body["model"],
            policies=(),
        )
        if not policy_decision.allowed:
            if audit_logger is not None:
                audit_logger.record_denial(
                    request_id=request_id,
                    denial_reason=policy_decision.denial_reason or "policy_denied",
                    authenticated=authenticated,
                    requested_model=body["model"],
                    resolved_model=resolved_model.bedrock_model_id,
                    policy_decision=policy_decision,
                )
            return error_response_for_exception(
                access_denied_error(
                    request_id,
                    message=f"Request blocked by policy: {policy_decision.denial_reason}.",
                ),
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
            if audit_logger is not None:
                audit_logger.record_denial(
                    request_id=request_id,
                    denial_reason=quota_decision.denial_reason or DENIAL_QUOTA_HARD_LIMIT_EXCEEDED,
                    authenticated=authenticated,
                    requested_model=body["model"],
                    resolved_model=resolved_model.bedrock_model_id,
                    policy_decision=policy_decision,
                )
            return error_response_for_exception(
                access_denied_error(
                    request_id,
                    message=f"Request blocked by quota: {quota_decision.denial_reason}.",
                ),
                request_id=request_id,
            )

        rate_limit_decision = dependencies.rate_limiter.check(authenticated.user.user_id)
        if not rate_limit_decision.allowed:
            headers = {}
            if rate_limit_decision.retry_after_seconds is not None:
                headers["Retry-After"] = str(rate_limit_decision.retry_after_seconds)
            if audit_logger is not None:
                audit_logger.record_denial(
                    request_id=request_id,
                    denial_reason=DENIAL_REASON_RATE_LIMITED,
                    authenticated=authenticated,
                    requested_model=body["model"],
                    resolved_model=resolved_model.bedrock_model_id,
                    policy_decision=policy_decision,
                )
            return error_response_for_exception(
                rate_limit_exceeded_error(
                    request_id,
                    headers=headers,
                ),
                request_id=request_id,
            )

        converse_request = build_converse_request(body, resolved_model=resolved_model)
        if converse_request.operation == "converse_stream":
            raw_stream = dependencies.bedrock_client.converse_stream(converse_request)
            decoder = ConverseStreamDecoder(model=body["model"])

            def _stream_with_audit():
                try:
                    yield from decoder.iter_sse_events(raw_stream)
                finally:
                    if audit_logger is not None:
                        audit_logger.record_success(
                            authenticated=authenticated,
                            request_id=request_id,
                            requested_model=body["model"],
                            resolved_model=resolved_model.bedrock_model_id,
                            policy_decision=policy_decision,
                            usage=decoder.final_usage,
                            usage_snapshot=quota_decision.usage_snapshot,
                            latency_ms=_elapsed_latency_ms(started_at),
                        )

            return StreamingResponse(
                _stream_with_audit(),
                media_type="text/event-stream",
            )

        raw_response = dependencies.bedrock_client.converse(converse_request)
        parsed_response = parse_converse_response(raw_response, model=body["model"])
        if audit_logger is not None:
            audit_logger.record_success(
                authenticated=authenticated,
                request_id=request_id,
                requested_model=body["model"],
                resolved_model=resolved_model.bedrock_model_id,
                policy_decision=policy_decision,
                usage=parsed_response["usage"],
                usage_snapshot=quota_decision.usage_snapshot,
                latency_ms=_elapsed_latency_ms(started_at),
            )
        return JSONResponse(status_code=200, content=parsed_response)
    except Exception as error:
        return error_response_for_exception(error, request_id=request_id)


@router.post("/v1/messages/count_tokens")
async def count_tokens(request: Request) -> JSONResponse:
    body = await request.json()
    dependencies = request.app.state.dependencies
    request_id = resolve_request_id(request)

    try:
        dependencies.auth_service.authenticate(
            request.headers.get("Authorization"),
            request_id=request_id,
        )
        resolved_model = dependencies.model_resolver.resolve(body["model"])
        converse_request = build_converse_request(body, resolved_model=resolved_model)
        count_response = dependencies.bedrock_client.count_tokens(converse_request)
    except Exception as error:
        return error_response_for_exception(error, request_id=request_id)

    input_tokens = int(
        count_response.get("inputTokens", count_response.get("input_tokens", 0)) or 0
    )
    return JSONResponse(status_code=200, content={"input_tokens": input_tokens})


def _elapsed_latency_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)
