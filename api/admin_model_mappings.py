from __future__ import annotations

from datetime import date
from typing import Protocol

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from api.admin_auth import require_admin_write
from models.domain import ModelPricingRecord, ModelRouteRecord

router = APIRouter()


class ModelRouteMutationStore(Protocol):
    def upsert_model_route(self, record: ModelRouteRecord) -> None: ...


class PricingCatalogMutationStore(Protocol):
    def upsert_pricing(self, record: ModelPricingRecord) -> None: ...


class ReloadNotifier(Protocol):
    def reload(self) -> None: ...


class ModelRouteUpdateRequest(BaseModel):
    logical_model: str
    provider: str
    bedrock_api_route: str
    bedrock_model_id: str | None = None
    inference_profile_id: str | None = None
    supports_native_structured_output: bool
    supports_reasoning: bool
    supports_prompt_cache_ttl: bool
    supports_disable_parallel_tool_use: bool
    priority: int
    is_active: bool = True


class PricingCatalogUpdateRequest(BaseModel):
    provider: str
    model_id: str
    input_cost_per_million: float
    output_cost_per_million: float
    cache_write_input_cost_per_million: float = 0.0
    cache_read_input_cost_per_million: float = 0.0
    currency: str = "USD"
    effective_from: date | None = None
    effective_to: date | None = None


class ModelMappingAdminService:
    def __init__(
        self,
        *,
        model_route_store: ModelRouteMutationStore,
        resolver_reload_notifier: ReloadNotifier,
        pricing_store: PricingCatalogMutationStore,
        pricing_reload_notifier: ReloadNotifier,
    ) -> None:
        self._model_route_store = model_route_store
        self._resolver_reload_notifier = resolver_reload_notifier
        self._pricing_store = pricing_store
        self._pricing_reload_notifier = pricing_reload_notifier

    def update_model_route(
        self,
        *,
        route_id: str,
        request: ModelRouteUpdateRequest,
    ) -> ModelRouteRecord:
        record = ModelRouteRecord(
            id=route_id,
            logical_model=request.logical_model,
            provider=request.provider,
            bedrock_api_route=request.bedrock_api_route,
            bedrock_model_id=request.bedrock_model_id,
            inference_profile_id=request.inference_profile_id,
            supports_native_structured_output=request.supports_native_structured_output,
            supports_reasoning=request.supports_reasoning,
            supports_prompt_cache_ttl=request.supports_prompt_cache_ttl,
            supports_disable_parallel_tool_use=request.supports_disable_parallel_tool_use,
            priority=request.priority,
            is_active=request.is_active,
        )
        self._model_route_store.upsert_model_route(record)
        self._resolver_reload_notifier.reload()
        return record

    def update_pricing_catalog(
        self,
        *,
        pricing_id: str,
        request: PricingCatalogUpdateRequest,
    ) -> ModelPricingRecord:
        record = ModelPricingRecord(
            id=pricing_id,
            provider=request.provider,
            model_id=request.model_id,
            input_cost_per_million=request.input_cost_per_million,
            output_cost_per_million=request.output_cost_per_million,
            cache_write_input_cost_per_million=request.cache_write_input_cost_per_million,
            cache_read_input_cost_per_million=request.cache_read_input_cost_per_million,
            currency=request.currency,
            effective_from=request.effective_from,
            effective_to=request.effective_to,
        )
        self._pricing_store.upsert_pricing(record)
        self._pricing_reload_notifier.reload()
        return record


@router.put("/admin/model-routes/{route_id}")
def update_model_route(
    route_id: str,
    request: Request,
    payload: ModelRouteUpdateRequest,
) -> dict[str, object]:
    require_admin_write(request)
    record = _model_mapping_service(request).update_model_route(route_id=route_id, request=payload)
    return jsonable_encoder(record)


@router.put("/admin/pricing-catalog/{pricing_id}")
def update_pricing_catalog(
    pricing_id: str,
    request: Request,
    payload: PricingCatalogUpdateRequest,
) -> dict[str, object]:
    require_admin_write(request)
    record = _model_mapping_service(request).update_pricing_catalog(
        pricing_id=pricing_id,
        request=payload,
    )
    return jsonable_encoder(record)


def _model_mapping_service(request: Request) -> ModelMappingAdminService:
    service = request.app.state.dependencies.model_mapping_service
    if service is None:
        raise HTTPException(status_code=500, detail="Model mapping service is not configured.")
    return service
