from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import AppDependencies
from models.domain import UserRecord
from proxy.model_resolver import ResolvedModel, ResolvedModelCapabilities
from tests.api.runtime_stubs import (
    AuthServiceStub,
    BedrockClientStub,
    ResolverStub,
    build_authenticated_request_context,
)


def test_count_tokens_uses_auth_resolver_and_converse_normalization() -> None:
    user = UserRecord(id="user-1", email="dev@example.com", display_name="Dev")
    bedrock_client = BedrockClientStub(count_tokens_response={"inputTokens": 123})
    app = create_app(
        AppDependencies(
            auth_service=AuthServiceStub(
                authenticated=build_authenticated_request_context(user)
            ),
            model_resolver=ResolverStub(_resolved_model()),
            bedrock_client=bedrock_client,
            request_id_generator=lambda: "req-count-1",
        )
    )

    response = TestClient(app).post(
        "/v1/messages/count_tokens",
        headers={"Authorization": "Bearer vk_valid"},
        json={
            "model": "claude-sonnet-4-5",
            "system": "Be concise.",
            "messages": [{"role": "user", "content": "hello"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"input_tokens": 123}
    assert len(bedrock_client.count_tokens_calls) == 1
    assert bedrock_client.count_tokens_calls[0].payload["system"] == [{"text": "Be concise."}]
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
