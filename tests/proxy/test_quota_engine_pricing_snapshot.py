from __future__ import annotations

from datetime import date

from models.domain import BudgetMetricType, BudgetPeriodType, BudgetPolicyRecord, ModelPricingRecord
from proxy.quota_engine import QuotaEngine, TokenUsageEstimate
from tests.fakes import InMemoryPricingRepository


def test_quota_engine_uses_one_pricing_snapshot_per_evaluation() -> None:
    repository = InMemoryPricingRepository(
        ModelPricingRecord(
            id="price-v1",
            provider="bedrock",
            model_id="anthropic.custom-v1:0",
            input_cost_per_million=3.0,
            output_cost_per_million=15.0,
            cache_write_input_cost_per_million=0.3,
            cache_read_input_cost_per_million=0.03,
            effective_from=date(2026, 1, 1),
        )
    )
    engine = QuotaEngine(pricing_repository=repository)
    policy = BudgetPolicyRecord(
        id="budget-user-cost",
        scope_type="user",
        scope_id="user-1",
        period_type=BudgetPeriodType.MONTH,
        metric_type=BudgetMetricType.COST_USD,
        limit_value=100,
        soft_limit_percent=80,
        hard_limit_percent=100,
    )
    token_usage = TokenUsageEstimate(
        input_tokens=1_000,
        output_tokens=500,
        cache_write_input_tokens=100,
        cache_read_input_tokens=200,
    )

    before_reload = engine.evaluate(
        budget_policies=[policy],
        current_usage=0.0,
        requested_usage=None,
        model_id="anthropic.custom-v1:0",
        token_usage=token_usage,
    )

    repository.stage_reload(
        ModelPricingRecord(
            id="price-v2",
            provider="bedrock",
            model_id="anthropic.custom-v1:0",
            input_cost_per_million=4.0,
            output_cost_per_million=20.0,
            cache_write_input_cost_per_million=0.4,
            cache_read_input_cost_per_million=0.04,
            effective_from=date(2026, 2, 1),
        )
    )
    repository.reload()

    after_reload = engine.evaluate(
        budget_policies=[policy],
        current_usage=0.0,
        requested_usage=None,
        model_id="anthropic.custom-v1:0",
        token_usage=token_usage,
    )

    assert before_reload.allowed is True
    assert before_reload.pricing_catalog_id == "price-v1"
    assert before_reload.usage_snapshot is not None
    assert before_reload.usage_snapshot.pricing_catalog_id == "price-v1"
    assert round(before_reload.usage_snapshot.estimated_total_cost_usd, 6) == 0.010536

    assert after_reload.allowed is True
    assert after_reload.pricing_catalog_id == "price-v2"
    assert after_reload.usage_snapshot is not None
    assert after_reload.usage_snapshot.pricing_catalog_id == "price-v2"
    assert round(after_reload.usage_snapshot.estimated_total_cost_usd, 6) == 0.014048
    assert repository.get_active_pricing_calls == [
        "anthropic.custom-v1:0",
        "anthropic.custom-v1:0",
    ]
    assert repository.reload_calls == 1
