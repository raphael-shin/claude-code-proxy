from __future__ import annotations

import json

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


def test_messages_streaming_maps_converse_events_to_anthropic_sse() -> None:
    user = UserRecord(id="user-1", email="dev@example.com", display_name="Dev")
    bedrock_client = BedrockClientStub(
        converse_stream_response=[
            {"messageStart": {"role": "assistant"}},
            {"contentBlockStart": {"contentBlockIndex": 0, "start": {"text": {}}}},
            {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "Hello"}}},
            {"contentBlockStop": {"contentBlockIndex": 0}},
            {"messageStop": {"stopReason": "end_turn"}},
            {
                "metadata": {
                    "usage": {
                        "inputTokens": 10,
                        "outputTokens": 20,
                        "totalTokens": 30,
                    }
                }
            },
        ]
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
            request_id_generator=lambda: "req-stream-1",
        )
    )

    with TestClient(app).stream(
        "POST",
        "/v1/messages",
        headers={"Authorization": "Bearer vk_valid"},
        json={
            "model": "claude-sonnet-4-5",
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
        },
    ) as response:
        lines = []
        iterator = response.iter_lines()
        for _ in range(4):
            lines.append(next(iterator))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert lines[0] == "event: message_start"
    first_payload = json.loads(lines[1].removeprefix("data: "))
    assert first_payload["type"] == "message_start"
    assert bedrock_client.stream_events_yielded >= 1


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
