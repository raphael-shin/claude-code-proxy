from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import AppDependencies
from models.domain import UserRecord
from proxy.model_resolver import ResolvedModel, ResolvedModelCapabilities
from proxy.policy_engine import DENIAL_MODEL_DENIED, PolicyDecision
from proxy.quota_engine import DENIAL_QUOTA_HARD_LIMIT_EXCEEDED, QuotaDecision
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


@pytest.mark.parametrize(
    ("policy_decision", "quota_decision", "rate_limit_decision", "status_code", "error_type"),
    [
        (
            PolicyDecision(allowed=False, denial_reason=DENIAL_MODEL_DENIED),
            QuotaDecision(
                allowed=True,
                denial_reason=None,
                effective_policy=None,
                soft_limit_reached=False,
                hard_limit_reached=False,
                projected_usage=0.0,
            ),
            RateLimitDecision(allowed=True),
            403,
            "permission_error",
        ),
        (
            PolicyDecision(allowed=True),
            QuotaDecision(
                allowed=False,
                denial_reason=DENIAL_QUOTA_HARD_LIMIT_EXCEEDED,
                effective_policy=None,
                soft_limit_reached=True,
                hard_limit_reached=True,
                projected_usage=100.0,
            ),
            RateLimitDecision(allowed=True),
            403,
            "permission_error",
        ),
        (
            PolicyDecision(allowed=True),
            QuotaDecision(
                allowed=True,
                denial_reason=None,
                effective_policy=None,
                soft_limit_reached=False,
                hard_limit_reached=False,
                projected_usage=0.0,
            ),
            RateLimitDecision(allowed=False, retry_after_seconds=17),
            429,
            "rate_limit_error",
        ),
    ],
)
def test_messages_fail_closed_before_bedrock_on_policy_quota_or_rate_limit(
    policy_decision: PolicyDecision,
    quota_decision: QuotaDecision,
    rate_limit_decision: RateLimitDecision,
    status_code: int,
    error_type: str,
) -> None:
    user = UserRecord(id="user-1", email="dev@example.com", display_name="Dev")
    bedrock_client = BedrockClientStub()
    app = create_app(
        AppDependencies(
            auth_service=AuthServiceStub(
                authenticated=build_authenticated_request_context(user)
            ),
            model_resolver=ResolverStub(_resolved_model()),
            policy_engine=PolicyEngineStub(policy_decision),
            quota_engine=QuotaEngineStub(quota_decision),
            rate_limiter=RateLimiterStub(rate_limit_decision),
            bedrock_client=bedrock_client,
            request_id_generator=lambda: "req-fail-closed",
        )
    )

    response = TestClient(app).post(
        "/v1/messages",
        headers={"Authorization": "Bearer vk_valid"},
        json={"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == status_code
    assert response.json()["type"] == "error"
    assert response.json()["error"]["type"] == error_type
    assert response.json()["request_id"] == "req-fail-closed"
    assert bedrock_client.converse_calls == []


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
