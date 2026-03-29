from __future__ import annotations

from models.domain import BudgetMetricType, BudgetPeriodType, BudgetPolicyRecord
from proxy.quota_engine import QuotaEngine


def test_quota_engine_tracks_soft_limit_without_blocking() -> None:
    engine = QuotaEngine()
    policy = BudgetPolicyRecord(
        id="budget-user",
        scope_type="user",
        scope_id="user-1",
        period_type=BudgetPeriodType.DAY,
        metric_type=BudgetMetricType.TOKENS,
        limit_value=1_000,
        soft_limit_percent=50,
        hard_limit_percent=90,
    )

    decision = engine.evaluate(
        budget_policies=[policy],
        current_usage=450,
        requested_usage=100,
    )

    assert decision.allowed is True
    assert decision.denial_reason is None
    assert decision.effective_policy == policy
    assert decision.soft_limit_reached is True
    assert decision.hard_limit_reached is False
    assert decision.projected_usage == 550.0


def test_quota_engine_blocks_when_projected_usage_reaches_hard_limit() -> None:
    engine = QuotaEngine()
    policy = BudgetPolicyRecord(
        id="budget-user",
        scope_type="user",
        scope_id="user-1",
        period_type=BudgetPeriodType.DAY,
        metric_type=BudgetMetricType.TOKENS,
        limit_value=1_000,
        soft_limit_percent=50,
        hard_limit_percent=90,
    )

    decision = engine.evaluate(
        budget_policies=[policy],
        current_usage=850,
        requested_usage=50,
    )

    assert decision.allowed is False
    assert decision.denial_reason == "quota_hard_limit_exceeded"
    assert decision.soft_limit_reached is True
    assert decision.hard_limit_reached is True
    assert decision.projected_usage == 900.0
