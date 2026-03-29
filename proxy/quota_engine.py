from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from models.domain import BudgetMetricType, BudgetPolicyRecord, ModelPricingRecord
from repositories.pricing_repository import PricingRepository

MILLION = 1_000_000
DENIAL_QUOTA_HARD_LIMIT_EXCEEDED = "quota_hard_limit_exceeded"
SCOPE_RANK = {
    "user": 0,
    "team": 1,
    "global": 2,
}


@dataclass(frozen=True, slots=True)
class TokenUsageEstimate:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass(frozen=True, slots=True)
class UsageCostSnapshot:
    pricing_catalog_id: str
    estimated_input_cost_usd: float
    estimated_output_cost_usd: float
    estimated_cache_write_cost_usd: float
    estimated_cache_read_cost_usd: float
    estimated_total_cost_usd: float


@dataclass(frozen=True, slots=True)
class QuotaDecision:
    allowed: bool
    denial_reason: str | None
    effective_policy: BudgetPolicyRecord | None
    soft_limit_reached: bool
    hard_limit_reached: bool
    projected_usage: float
    usage_snapshot: UsageCostSnapshot | None = None

    @property
    def pricing_catalog_id(self) -> str | None:
        return self.usage_snapshot.pricing_catalog_id if self.usage_snapshot else None


class QuotaEngine:
    def __init__(self, *, pricing_repository: PricingRepository | None = None) -> None:
        self._pricing_repository = pricing_repository

    def evaluate(
        self,
        *,
        budget_policies: Sequence[BudgetPolicyRecord],
        current_usage: float,
        requested_usage: float | None = None,
        model_id: str | None = None,
        token_usage: TokenUsageEstimate | None = None,
    ) -> QuotaDecision:
        effective_policy = self._select_effective_policy(budget_policies)
        pricing = self._get_active_pricing(model_id=model_id)
        usage_snapshot = self._build_usage_snapshot(pricing=pricing, token_usage=token_usage)

        resolved_requested_usage = self._resolve_requested_usage(
            effective_policy=effective_policy,
            requested_usage=requested_usage,
            usage_snapshot=usage_snapshot,
        )
        projected_usage = float(current_usage) + resolved_requested_usage

        if effective_policy is None:
            return QuotaDecision(
                allowed=True,
                denial_reason=None,
                effective_policy=None,
                soft_limit_reached=False,
                hard_limit_reached=False,
                projected_usage=projected_usage,
                usage_snapshot=usage_snapshot,
            )

        soft_limit = self._effective_limit_value(
            limit_value=effective_policy.limit_value,
            percent=effective_policy.soft_limit_percent,
        )
        hard_limit = self._effective_limit_value(
            limit_value=effective_policy.limit_value,
            percent=effective_policy.hard_limit_percent,
        )
        soft_limit_reached = projected_usage >= soft_limit
        hard_limit_reached = projected_usage >= hard_limit

        return QuotaDecision(
            allowed=not hard_limit_reached,
            denial_reason=DENIAL_QUOTA_HARD_LIMIT_EXCEEDED if hard_limit_reached else None,
            effective_policy=effective_policy,
            soft_limit_reached=soft_limit_reached,
            hard_limit_reached=hard_limit_reached,
            projected_usage=projected_usage,
            usage_snapshot=usage_snapshot,
        )

    def _select_effective_policy(
        self,
        policies: Sequence[BudgetPolicyRecord],
    ) -> BudgetPolicyRecord | None:
        active_policies = [policy for policy in policies if policy.is_active]
        if not active_policies:
            return None
        return min(
            active_policies,
            key=lambda policy: (
                self._effective_limit_value(
                    limit_value=policy.limit_value,
                    percent=policy.hard_limit_percent,
                ),
                policy.limit_value,
                policy.hard_limit_percent,
                SCOPE_RANK.get(policy.scope_type, 99),
                policy.id,
            ),
        )

    @staticmethod
    def _effective_limit_value(*, limit_value: int, percent: int) -> float:
        return float(limit_value) * (float(percent) / 100.0)

    def _get_active_pricing(self, *, model_id: str | None) -> ModelPricingRecord | None:
        if self._pricing_repository is None or model_id is None:
            return None
        return self._pricing_repository.get_active_pricing(model_id=model_id)

    @staticmethod
    def _build_usage_snapshot(
        *,
        pricing: ModelPricingRecord | None,
        token_usage: TokenUsageEstimate | None,
    ) -> UsageCostSnapshot | None:
        if pricing is None or token_usage is None:
            return None

        input_cost = token_usage.input_tokens * pricing.input_cost_per_million / MILLION
        output_cost = token_usage.output_tokens * pricing.output_cost_per_million / MILLION
        cache_write_cost = (
            token_usage.cache_write_input_tokens * pricing.cache_write_input_cost_per_million / MILLION
        )
        cache_read_cost = (
            token_usage.cache_read_input_tokens * pricing.cache_read_input_cost_per_million / MILLION
        )
        total_cost = input_cost + output_cost + cache_write_cost + cache_read_cost

        return UsageCostSnapshot(
            pricing_catalog_id=pricing.id,
            estimated_input_cost_usd=input_cost,
            estimated_output_cost_usd=output_cost,
            estimated_cache_write_cost_usd=cache_write_cost,
            estimated_cache_read_cost_usd=cache_read_cost,
            estimated_total_cost_usd=total_cost,
        )

    @staticmethod
    def _resolve_requested_usage(
        *,
        effective_policy: BudgetPolicyRecord | None,
        requested_usage: float | None,
        usage_snapshot: UsageCostSnapshot | None,
    ) -> float:
        if requested_usage is not None:
            return float(requested_usage)
        if effective_policy is None:
            return 0.0
        if effective_policy.metric_type == BudgetMetricType.COST_USD and usage_snapshot is not None:
            return usage_snapshot.estimated_total_cost_usd
        return 0.0
