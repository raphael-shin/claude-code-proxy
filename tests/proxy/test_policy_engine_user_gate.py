from __future__ import annotations

import pytest

from models.domain import PolicyRecord, UserRecord
from proxy.policy_engine import PolicyEngine


@pytest.mark.parametrize(
    ("user", "expected_reason"),
    [
        (
            UserRecord(
                id="user-1",
                email="dev@example.com",
                display_name="Dev",
                is_active=False,
            ),
            "user_inactive",
        ),
        (
            UserRecord(
                id="user-1",
                email="dev@example.com",
                display_name="Dev",
                proxy_access_enabled=False,
            ),
            "proxy_access_disabled",
        ),
    ],
)
def test_policy_engine_rejects_user_before_policy_evaluation(
    user: UserRecord,
    expected_reason: str,
) -> None:
    engine = PolicyEngine()

    decision = engine.evaluate(
        user=user,
        model="claude-sonnet-4-20250514",
        policies=[
            PolicyRecord(
                id="allow-sonnet",
                scope_type="user",
                scope_id="user-1",
                rule_type="allow_model",
                rule_value="claude-sonnet-*",
            )
        ],
    )

    assert decision.allowed is False
    assert decision.denial_reason == expected_reason
    assert decision.effective_max_output_tokens is None
    assert decision.trace.evaluated_scopes == ("user_status",)
    assert decision.trace.matched_policy_ids == ()
