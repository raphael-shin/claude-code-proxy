from __future__ import annotations

from fastapi.testclient import TestClient

from api.admin_model_mappings import ModelMappingAdminService
from api.app import create_app
from api.dependencies import AppDependencies
from tests.admin.support import (
    InMemoryAdminIdentityRepository,
    InMemoryModelRouteStore,
    InMemoryPricingStore,
    ReloadNotifier,
    admin_headers,
)


def test_model_mapping_and_pricing_updates_trigger_reload_hooks() -> None:
    resolver_notifier = ReloadNotifier()
    pricing_notifier = ReloadNotifier()
    route_store = InMemoryModelRouteStore()
    pricing_store = InMemoryPricingStore()
    dependencies = AppDependencies(
        admin_identity_repository=InMemoryAdminIdentityRepository(
            {"principal:operator": "operator"}
        ),
        model_mapping_service=ModelMappingAdminService(
            model_route_store=route_store,
            resolver_reload_notifier=resolver_notifier,
            pricing_store=pricing_store,
            pricing_reload_notifier=pricing_notifier,
        ),
    )
    client = TestClient(create_app(dependencies))

    route_response = client.put(
        "/admin/model-routes/route-1",
        headers=admin_headers("principal:operator"),
        json={
            "logical_model": "sonnet",
            "provider": "bedrock",
            "bedrock_api_route": "converse",
            "bedrock_model_id": "anthropic.claude-sonnet-4-5-v1:0",
            "inference_profile_id": None,
            "supports_native_structured_output": True,
            "supports_reasoning": True,
            "supports_prompt_cache_ttl": True,
            "supports_disable_parallel_tool_use": True,
            "priority": 100,
            "is_active": True,
        },
    )
    pricing_response = client.put(
        "/admin/pricing-catalog/pricing-1",
        headers=admin_headers("principal:operator"),
        json={
            "provider": "bedrock",
            "model_id": "anthropic.claude-sonnet-4-5-v1:0",
            "input_cost_per_million": 3.0,
            "output_cost_per_million": 15.0,
            "cache_write_input_cost_per_million": 0.3,
            "cache_read_input_cost_per_million": 0.03,
        },
    )

    assert route_response.status_code == 200
    assert pricing_response.status_code == 200
    assert resolver_notifier.reload_calls == 1
    assert pricing_notifier.reload_calls == 1
    assert "route-1" in route_store.records
    assert "pricing-1" in pricing_store.records
