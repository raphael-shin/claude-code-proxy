from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import AppDependencies
from models.domain import UserRecord
from models.errors import authentication_failed_error
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


def test_messages_requires_auth_before_any_other_dependency_runs() -> None:
    user = UserRecord(id="user-1", email="dev@example.com", display_name="Dev")
    dependencies = AppDependencies(
        auth_service=AuthServiceStub(
            error=authentication_failed_error(
                "req-auth-fail",
                details={"reason": "missing_bearer_token"},
            )
        ),
        model_resolver=ResolverStub(_resolved_model()),
        policy_engine=PolicyEngineStub(PolicyDecision(allowed=True)),
        quota_engine=QuotaEngineStub(
            QuotaDecision(
                allowed=True,
                denial_reason=None,
                effective_policy=None,
                soft_limit_reached=False,
                hard_limit_reached=False,
                projected_usage=0.0,
            )
        ),
        rate_limiter=RateLimiterStub(RateLimitDecision(allowed=True)),
        bedrock_client=BedrockClientStub(),
        request_id_generator=lambda: "req-auth-fail",
    )
    app = create_app(dependencies)

    response = TestClient(app).post(
        "/v1/messages",
        json={"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 401
    assert response.json() == {
        "type": "error",
        "error": {
            "type": "authentication_error",
            "message": "Authentication failed.",
            "details": {"reason": "missing_bearer_token"},
        },
        "request_id": "req-auth-fail",
    }
    assert dependencies.model_resolver.calls == []
    assert dependencies.policy_engine.calls == []
    assert dependencies.quota_engine.calls == []
    assert dependencies.rate_limiter.calls == []
    assert dependencies.bedrock_client.converse_calls == []


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
