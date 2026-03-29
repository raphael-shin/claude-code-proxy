from __future__ import annotations

import pytest

from models.domain import ModelAliasRuleRecord, ModelRouteRecord
from proxy.model_resolver import ModelResolutionError, ModelResolver
from tests.fakes import InMemoryModelAliasRepository, InMemoryModelRouteRepository


def test_model_resolver_rejects_unknown_model_before_route_lookup() -> None:
    alias_repository = InMemoryModelAliasRepository(
        [
            ModelAliasRuleRecord(
                id="alias-sonnet",
                pattern="claude-sonnet-*",
                logical_model="sonnet",
                priority=10,
            )
        ]
    )
    route_repository = InMemoryModelRouteRepository()
    resolver = ModelResolver(
        model_alias_repository=alias_repository,
        model_route_repository=route_repository,
    )

    with pytest.raises(ModelResolutionError) as excinfo:
        resolver.resolve("claude-opus-4-20250514")

    assert excinfo.value.reason == "unknown_model"
    assert "claude-opus-4-20250514" in excinfo.value.message
    assert alias_repository.list_alias_rules_calls == 1
    assert route_repository.list_model_routes_calls == 0


def test_model_resolver_rejects_non_converse_route() -> None:
    alias_repository = InMemoryModelAliasRepository(
        [
            ModelAliasRuleRecord(
                id="alias-legacy",
                pattern="claude-legacy-*",
                logical_model="legacy",
                priority=10,
            )
        ]
    )
    route_repository = InMemoryModelRouteRepository(
        [
            ModelRouteRecord(
                id="route-converse-fallback",
                logical_model="legacy",
                provider="bedrock",
                bedrock_api_route="converse",
                bedrock_model_id="anthropic.legacy-converse-v1:0",
                inference_profile_id=None,
                supports_native_structured_output=False,
                supports_reasoning=False,
                supports_prompt_cache_ttl=False,
                supports_disable_parallel_tool_use=False,
                priority=1,
            ),
            ModelRouteRecord(
                id="route-legacy",
                logical_model="legacy",
                provider="bedrock",
                bedrock_api_route="invoke_model",
                bedrock_model_id="anthropic.legacy-v1:0",
                inference_profile_id=None,
                supports_native_structured_output=False,
                supports_reasoning=False,
                supports_prompt_cache_ttl=False,
                supports_disable_parallel_tool_use=False,
                priority=100,
            ),
        ]
    )
    resolver = ModelResolver(
        model_alias_repository=alias_repository,
        model_route_repository=route_repository,
    )

    with pytest.raises(ModelResolutionError) as excinfo:
        resolver.resolve("claude-legacy-2")

    assert excinfo.value.reason == "unsupported_model_route"
    assert "invoke_model" in excinfo.value.message
    assert alias_repository.list_alias_rules_calls == 1
    assert route_repository.list_model_routes_calls == 1
