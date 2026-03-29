from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase

from models.domain import ModelAliasRuleRecord, ModelRouteRecord
from repositories.model_alias_repository import ModelAliasRepository
from repositories.model_route_repository import ModelRouteRepository

REASON_UNKNOWN_MODEL = "unknown_model"
REASON_UNSUPPORTED_ROUTE = "unsupported_model_route"


@dataclass(frozen=True, slots=True)
class ResolvedModelCapabilities:
    supports_native_structured_output: bool
    supports_reasoning: bool
    supports_prompt_cache_ttl: bool
    supports_disable_parallel_tool_use: bool

    @classmethod
    def from_route(cls, route: ModelRouteRecord) -> ResolvedModelCapabilities:
        return cls(
            supports_native_structured_output=route.supports_native_structured_output,
            supports_reasoning=route.supports_reasoning,
            supports_prompt_cache_ttl=route.supports_prompt_cache_ttl,
            supports_disable_parallel_tool_use=route.supports_disable_parallel_tool_use,
        )


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    requested_model: str
    logical_model: str
    provider: str
    bedrock_api_route: str
    bedrock_model_id: str | None
    inference_profile_id: str | None
    aws_region_name: str | None
    capabilities: ResolvedModelCapabilities


class ModelResolutionError(Exception):
    def __init__(self, *, requested_model: str, reason: str, message: str) -> None:
        super().__init__(message)
        self.requested_model = requested_model
        self.reason = reason
        self.message = message


class ModelResolver:
    def __init__(
        self,
        *,
        model_alias_repository: ModelAliasRepository,
        model_route_repository: ModelRouteRepository,
    ) -> None:
        self._model_alias_repository = model_alias_repository
        self._model_route_repository = model_route_repository

    def resolve(self, requested_model: str) -> ResolvedModel:
        alias_rule = self._find_alias_rule(requested_model)
        if alias_rule is None:
            raise ModelResolutionError(
                requested_model=requested_model,
                reason=REASON_UNKNOWN_MODEL,
                message=f"Model '{requested_model}' is not allowed.",
            )

        route = self._find_route(alias_rule.logical_model)
        if route is None:
            raise ModelResolutionError(
                requested_model=requested_model,
                reason=REASON_UNSUPPORTED_ROUTE,
                message=f"Logical model '{alias_rule.logical_model}' has no supported Bedrock Converse route.",
            )
        if route.bedrock_api_route != "converse":
            raise ModelResolutionError(
                requested_model=requested_model,
                reason=REASON_UNSUPPORTED_ROUTE,
                message=(
                    f"Logical model '{alias_rule.logical_model}' resolves to "
                    f"unsupported Bedrock route '{route.bedrock_api_route}'."
                ),
            )

        return ResolvedModel(
            requested_model=requested_model,
            logical_model=alias_rule.logical_model,
            provider=route.provider,
            bedrock_api_route=route.bedrock_api_route,
            bedrock_model_id=route.bedrock_model_id,
            inference_profile_id=route.inference_profile_id,
            aws_region_name=None,
            capabilities=ResolvedModelCapabilities.from_route(route),
        )

    def _find_alias_rule(self, requested_model: str) -> ModelAliasRuleRecord | None:
        matching_rules = [
            rule
            for rule in self._model_alias_repository.list_alias_rules()
            if rule.is_active and fnmatchcase(requested_model, rule.pattern)
        ]
        return self._select_highest_priority(matching_rules)

    def _find_route(self, logical_model: str) -> ModelRouteRecord | None:
        matching_routes = [
            route
            for route in self._model_route_repository.list_model_routes()
            if route.is_active and route.logical_model == logical_model
        ]
        return self._select_highest_priority(matching_routes)

    @staticmethod
    def _select_highest_priority(records: list[ModelAliasRuleRecord] | list[ModelRouteRecord]) -> ModelAliasRuleRecord | ModelRouteRecord | None:
        if not records:
            return None
        return max(records, key=lambda record: record.priority)
