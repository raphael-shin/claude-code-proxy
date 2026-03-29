from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import AppDependencies
from models.domain import UserRecord
from proxy.model_resolver import ResolvedModel, ResolvedModelCapabilities
from proxy.policy_engine import PolicyDecision
from proxy.quota_engine import QuotaDecision
from proxy.rate_limiter import RateLimitDecision
from tests.api.runtime_stubs import (
    AuthServiceStub,
    BedrockClientStub,
    PolicyEngineStub,
    QuotaEngineStub,
    RateLimiterStub,
    ResolverStub,
    build_authenticated_request_context,
)


def test_messages_pipeline_calls_dependencies_in_order_once() -> None:
    call_log: list[str] = []
    user = UserRecord(id="user-1", email="dev@example.com", display_name="Dev")
    app = create_app(
        AppDependencies(
            auth_service=AuthServiceStub(
                authenticated=build_authenticated_request_context(user),
                call_log=call_log,
            ),
            model_resolver=ResolverStub(_resolved_model(), call_log=call_log),
            policy_engine=PolicyEngineStub(PolicyDecision(allowed=True), call_log=call_log),
            quota_engine=QuotaEngineStub(
                QuotaDecision(
                    allowed=True,
                    denial_reason=None,
                    effective_policy=None,
                    soft_limit_reached=False,
                    hard_limit_reached=False,
                    projected_usage=0.0,
                ),
                call_log=call_log,
            ),
            rate_limiter=RateLimiterStub(RateLimitDecision(allowed=True), call_log=call_log),
            bedrock_client=BedrockClientStub(
                converse_response={
                    "output": {"message": {"role": "assistant", "content": [{"text": "ok"}]}},
                    "stopReason": "end_turn",
                    "usage": {},
                },
                call_log=call_log,
            ),
            request_id_generator=lambda: "req-order-1",
        )
    )

    response = TestClient(app).post(
        "/v1/messages",
        headers={"Authorization": "Bearer vk_valid"},
        json={"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200
    assert call_log == ["auth", "resolve", "policy", "quota", "rate_limit", "bedrock"]


def _resolved_model() -> ResolvedModel:
    return ResolvedModel(
        requested_model="claude-sonnet-4-5",
        logical_model="sonnet",
        provider="bedrock",
        bedrock_api_route="converse",
        bedrock_model_id="anthropic.claude-sonnet-4-5-v1:0",
        inference_profile_id=None,
        aws_region_name="us-east-1",
        capabilities=ResolvedModelCapabilities(
            supports_native_structured_output=True,
            supports_reasoning=True,
            supports_prompt_cache_ttl=True,
            supports_disable_parallel_tool_use=True,
        ),
    )
