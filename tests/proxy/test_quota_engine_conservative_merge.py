from __future__ import annotations

from models.domain import BudgetMetricType, BudgetPeriodType, BudgetPolicyRecord
from proxy.quota_engine import QuotaEngine


def test_quota_engine_selects_most_conservative_policy_across_scopes() -> None:
    engine = QuotaEngine()
    user_policy = BudgetPolicyRecord(
        id="budget-user",
        scope_type="user",
        scope_id="user-1",
        period_type=BudgetPeriodType.MONTH,
        metric_type=BudgetMetricType.TOKENS,
        limit_value=1_000,
        soft_limit_percent=80,
        hard_limit_percent=90,
    )
    team_policy_a = BudgetPolicyRecord(
        id="budget-team-a",
        scope_type="team",
        scope_id="team-a",
        period_type=BudgetPeriodType.MONTH,
        metric_type=BudgetMetricType.TOKENS,
        limit_value=900,
        soft_limit_percent=70,
        hard_limit_percent=80,
    )
    team_policy_b = BudgetPolicyRecord(
        id="budget-team-b",
        scope_type="team",
        scope_id="team-b",
        period_type=BudgetPeriodType.MONTH,
        metric_type=BudgetMetricType.TOKENS,
        limit_value=700,
        soft_limit_percent=70,
        hard_limit_percent=85,
    )
    global_policy = BudgetPolicyRecord(
        id="budget-global",
        scope_type="global",
        scope_id="default",
        period_type=BudgetPeriodType.MONTH,
        metric_type=BudgetMetricType.TOKENS,
        limit_value=950,
        soft_limit_percent=60,
        hard_limit_percent=75,
    )

    decision = engine.evaluate(
        budget_policies=[user_policy, team_policy_a, team_policy_b, global_policy],
        current_usage=580,
        requested_usage=20,
    )

    assert decision.allowed is False
    assert decision.denial_reason == "quota_hard_limit_exceeded"
    assert decision.effective_policy == team_policy_b
    assert decision.soft_limit_reached is True
    assert decision.hard_limit_reached is True
    assert decision.projected_usage == 600.0
