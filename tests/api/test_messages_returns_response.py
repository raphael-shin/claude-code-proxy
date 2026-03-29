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


def test_messages_returns_non_streaming_anthropic_response() -> None:
    user = UserRecord(
        id="user-1",
        email="dev@example.com",
        display_name="Dev",
        groups=("eng",),
        department="platform",
    )
    bedrock_client = BedrockClientStub(
        converse_response={
            "requestMetadata": {"requestId": "msg-bedrock-1"},
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Hello back"}],
                }
            },
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": 11,
                "outputTokens": 22,
                "totalTokens": 33,
            },
        }
    )
    app = create_app(
        AppDependencies(
            auth_service=AuthServiceStub(
                authenticated=build_authenticated_request_context(user)
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
            bedrock_client=bedrock_client,
            request_id_generator=lambda: "req-runtime-1",
        )
    )

    response = TestClient(app).post(
        "/v1/messages",
        headers={"Authorization": "Bearer vk_valid"},
        json={
            "model": "claude-sonnet-4-5",
            "system": "Be concise.",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "msg-bedrock-1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-4-5",
        "content": [{"type": "text", "text": "Hello back"}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": 11,
            "output_tokens": 22,
            "total_tokens": 33,
            "cache_write_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_details": None,
        },
    }
    assert len(bedrock_client.converse_calls) == 1
    assert bedrock_client.converse_calls[0].operation == "converse"


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
