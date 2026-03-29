from __future__ import annotations

from models.domain import ModelAliasRuleRecord, ModelRouteRecord
from proxy.model_resolver import ModelResolver
from tests.fakes import InMemoryModelAliasRepository, InMemoryModelRouteRepository


def test_model_resolver_keeps_feature_gates_disabled_when_route_says_false() -> None:
    resolver = ModelResolver(
        model_alias_repository=InMemoryModelAliasRepository(
            [
                ModelAliasRuleRecord(
                    id="alias-sonnet",
                    pattern="claude-sonnet-*",
                    logical_model="sonnet",
                    priority=10,
                )
            ]
        ),
        model_route_repository=InMemoryModelRouteRepository(
            [
                ModelRouteRecord(
                    id="route-sonnet",
                    logical_model="sonnet",
                    provider="bedrock",
                    bedrock_api_route="converse",
                    bedrock_model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                    inference_profile_id=None,
                    supports_native_structured_output=False,
                    supports_reasoning=False,
                    supports_prompt_cache_ttl=False,
                    supports_disable_parallel_tool_use=False,
                    priority=10,
                )
            ]
        ),
    )

    resolved = resolver.resolve("claude-sonnet-4-5-20250929")

    assert resolved.bedrock_api_route == "converse"
    assert resolved.capabilities.supports_native_structured_output is False
    assert resolved.capabilities.supports_reasoning is False
    assert resolved.capabilities.supports_prompt_cache_ttl is False
    assert resolved.capabilities.supports_disable_parallel_tool_use is False


def test_model_resolver_uses_route_capabilities_as_source_of_truth() -> None:
    resolver = ModelResolver(
        model_alias_repository=InMemoryModelAliasRepository(
            [
                ModelAliasRuleRecord(
                    id="alias-custom",
                    pattern="claude-custom-*",
                    logical_model="custom",
                    priority=10,
                )
            ]
        ),
        model_route_repository=InMemoryModelRouteRepository(
            [
                ModelRouteRecord(
                    id="route-custom",
                    logical_model="custom",
                    provider="bedrock",
                    bedrock_api_route="converse",
                    bedrock_model_id="anthropic.internal-custom-v1:0",
                    inference_profile_id="ip-custom",
                    supports_native_structured_output=True,
                    supports_reasoning=True,
                    supports_prompt_cache_ttl=True,
                    supports_disable_parallel_tool_use=True,
                    priority=10,
                )
            ]
        ),
    )

    resolved = resolver.resolve("claude-custom-preview")

    assert resolved.bedrock_model_id == "anthropic.internal-custom-v1:0"
    assert resolved.inference_profile_id == "ip-custom"
    assert resolved.capabilities.supports_native_structured_output is True
    assert resolved.capabilities.supports_reasoning is True
    assert resolved.capabilities.supports_prompt_cache_ttl is True
    assert resolved.capabilities.supports_disable_parallel_tool_use is True
