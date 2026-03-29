from __future__ import annotations

from models.domain import PolicyRecord, UserRecord
from proxy.policy_engine import PolicyEngine


def test_policy_engine_applies_scopes_in_order_and_prefers_deny() -> None:
    engine = PolicyEngine()
    user = UserRecord(
        id="user-1",
        email="dev@example.com",
        display_name="Dev",
        groups=("eng",),
        department="platform",
    )

    decision = engine.evaluate(
        user=user,
        model="claude-sonnet-4-20250514",
        policies=[
            PolicyRecord(
                id="global-allow",
                scope_type="global",
                scope_id="default",
                rule_type="allow_model",
                rule_value="claude-sonnet-*",
            ),
            PolicyRecord(
                id="department-limit",
                scope_type="department",
                scope_id="platform",
                rule_type="max_output_tokens",
                rule_value="4000",
            ),
            PolicyRecord(
                id="group-deny",
                scope_type="group",
                scope_id="eng",
                rule_type="deny_model",
                rule_value="claude-sonnet-*",
            ),
            PolicyRecord(
                id="user-allow",
                scope_type="user",
                scope_id="user-1",
                rule_type="allow_model",
                rule_value="claude-sonnet-*",
            ),
            PolicyRecord(
                id="global-limit",
                scope_type="global",
                scope_id="default",
                rule_type="max_output_tokens",
                rule_value="2000",
            ),
        ],
    )

    assert decision.allowed is False
    assert decision.denial_reason == "model_denied"
    assert decision.effective_max_output_tokens == 2000
    assert decision.trace.evaluated_scopes == (
        "user_status",
        "user:user-1",
        "group:eng",
        "department:platform",
        "global",
    )
    assert decision.trace.matched_policy_ids == (
        "user-allow",
        "group-deny",
        "department-limit",
        "global-allow",
        "global-limit",
    )


def test_policy_engine_keeps_most_restrictive_numeric_policy() -> None:
    engine = PolicyEngine()
    user = UserRecord(
        id="user-1",
        email="dev@example.com",
        display_name="Dev",
        groups=("eng",),
        department="platform",
    )

    decision = engine.evaluate(
        user=user,
        model="claude-sonnet-4-20250514",
        policies=[
            PolicyRecord(
                id="user-allow",
                scope_type="user",
                scope_id="user-1",
                rule_type="allow_model",
                rule_value="claude-sonnet-*",
            ),
            PolicyRecord(
                id="user-limit",
                scope_type="user",
                scope_id="user-1",
                rule_type="max_output_tokens",
                rule_value="8000",
            ),
            PolicyRecord(
                id="department-limit",
                scope_type="department",
                scope_id="platform",
                rule_type="max_output_tokens",
                rule_value="4000",
            ),
            PolicyRecord(
                id="global-limit",
                scope_type="global",
                scope_id="default",
                rule_type="max_output_tokens",
                rule_value="2000",
            ),
        ],
    )

    assert decision.allowed is True
    assert decision.denial_reason is None
    assert decision.effective_max_output_tokens == 2000
