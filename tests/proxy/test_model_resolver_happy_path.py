from __future__ import annotations

from models.domain import ModelAliasRuleRecord, ModelRouteRecord
from proxy.model_resolver import ModelResolver
from tests.fakes import InMemoryModelAliasRepository, InMemoryModelRouteRepository


def test_model_resolver_maps_request_model_to_converse_route() -> None:
    alias_repository = InMemoryModelAliasRepository(
        [
            ModelAliasRuleRecord(
                id="alias-generic",
                pattern="claude-*",
                logical_model="fallback",
                priority=1,
            ),
            ModelAliasRuleRecord(
                id="alias-sonnet",
                pattern="claude-sonnet-*",
                logical_model="sonnet",
                priority=10,
            ),
        ]
    )
    route_repository = InMemoryModelRouteRepository(
        [
            ModelRouteRecord(
                id="route-fallback",
                logical_model="fallback",
                provider="bedrock",
                bedrock_api_route="converse",
                bedrock_model_id="anthropic.fallback-v1:0",
                inference_profile_id=None,
                supports_native_structured_output=False,
                supports_reasoning=False,
                supports_prompt_cache_ttl=False,
                supports_disable_parallel_tool_use=False,
                priority=1,
            ),
            ModelRouteRecord(
                id="route-sonnet",
                logical_model="sonnet",
                provider="bedrock",
                bedrock_api_route="converse",
                bedrock_model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
                inference_profile_id="ip-sonnet-cross-region",
                supports_native_structured_output=True,
                supports_reasoning=True,
                supports_prompt_cache_ttl=True,
                supports_disable_parallel_tool_use=True,
                priority=10,
            ),
        ]
    )

    resolver = ModelResolver(
        model_alias_repository=alias_repository,
        model_route_repository=route_repository,
    )

    resolved = resolver.resolve("claude-sonnet-4-20250514")

    assert resolved.requested_model == "claude-sonnet-4-20250514"
    assert resolved.logical_model == "sonnet"
    assert resolved.provider == "bedrock"
    assert resolved.bedrock_api_route == "converse"
    assert resolved.bedrock_model_id == "us.anthropic.claude-sonnet-4-20250514-v1:0"
    assert resolved.inference_profile_id == "ip-sonnet-cross-region"
    assert resolved.aws_region_name is None
    assert resolved.capabilities.supports_native_structured_output is True
    assert resolved.capabilities.supports_reasoning is True
    assert resolved.capabilities.supports_prompt_cache_ttl is True
    assert resolved.capabilities.supports_disable_parallel_tool_use is True
    assert alias_repository.list_alias_rules_calls == 1
    assert route_repository.list_model_routes_calls == 1
