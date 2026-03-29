from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Sequence

from models.domain import PolicyRecord, UserRecord

MODEL_ALLOW_RULE = "allow_model"
MODEL_DENY_RULE = "deny_model"
MAX_OUTPUT_TOKENS_RULE = "max_output_tokens"


@dataclass(frozen=True, slots=True)
class PolicyEvaluationTrace:
    evaluated_scopes: tuple[str, ...] = ()
    matched_policy_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    denial_reason: str | None = None
    effective_max_output_tokens: int | None = None
    trace: PolicyEvaluationTrace = field(default_factory=PolicyEvaluationTrace)


class PolicyEngine:
    def evaluate(
        self,
        *,
        user: UserRecord,
        model: str,
        policies: Sequence[PolicyRecord],
    ) -> PolicyDecision:
        if not user.is_active:
            return PolicyDecision(
                allowed=False,
                denial_reason="user_inactive",
                trace=PolicyEvaluationTrace(evaluated_scopes=("user_status",)),
            )
        if not user.proxy_access_enabled:
            return PolicyDecision(
                allowed=False,
                denial_reason="proxy_access_disabled",
                trace=PolicyEvaluationTrace(evaluated_scopes=("user_status",)),
            )

        trace_scopes = ["user_status"]
        ordered_policies = self._collect_policies_by_scope(user=user, policies=policies, trace_scopes=trace_scopes)
        matched_policy_ids = tuple(policy.id for policy in ordered_policies)
        max_output_tokens = self._resolve_effective_max_output_tokens(ordered_policies)

        matching_deny = next(
            (
                policy
                for policy in ordered_policies
                if policy.rule_type == MODEL_DENY_RULE and self._rule_matches_model(policy, model)
            ),
            None,
        )
        if matching_deny is not None:
            return PolicyDecision(
                allowed=False,
                denial_reason="model_denied",
                effective_max_output_tokens=max_output_tokens,
                trace=PolicyEvaluationTrace(
                    evaluated_scopes=tuple(trace_scopes),
                    matched_policy_ids=matched_policy_ids,
                ),
            )

        model_access_rules = [
            policy for policy in ordered_policies if policy.rule_type in {MODEL_ALLOW_RULE, MODEL_DENY_RULE}
        ]
        has_matching_allow = any(
            policy.rule_type == MODEL_ALLOW_RULE and self._rule_matches_model(policy, model)
            for policy in model_access_rules
        )
        if model_access_rules and not has_matching_allow:
            return PolicyDecision(
                allowed=False,
                denial_reason="model_not_allowed",
                effective_max_output_tokens=max_output_tokens,
                trace=PolicyEvaluationTrace(
                    evaluated_scopes=tuple(trace_scopes),
                    matched_policy_ids=matched_policy_ids,
                ),
            )

        return PolicyDecision(
            allowed=True,
            effective_max_output_tokens=max_output_tokens,
            trace=PolicyEvaluationTrace(
                evaluated_scopes=tuple(trace_scopes),
                matched_policy_ids=matched_policy_ids,
            ),
        )

    def _collect_policies_by_scope(
        self,
        *,
        user: UserRecord,
        policies: Sequence[PolicyRecord],
        trace_scopes: list[str],
    ) -> list[PolicyRecord]:
        ordered: list[PolicyRecord] = []
        scopes: list[tuple[str, str | None]] = [("user", user.id)]
        scopes.extend(("group", group) for group in user.groups)
        scopes.append(("department", user.department))
        scopes.append(("global", None))

        for scope_type, scope_id in scopes:
            if scope_type == "department" and scope_id is None:
                continue
            if scope_type == "global":
                trace_scopes.append("global")
                ordered.extend(
                    policy for policy in policies if policy.is_active and policy.scope_type == "global"
                )
                continue

            trace_scopes.append(f"{scope_type}:{scope_id}")
            ordered.extend(
                policy
                for policy in policies
                if policy.is_active and policy.scope_type == scope_type and policy.scope_id == scope_id
            )

        return ordered

    @staticmethod
    def _resolve_effective_max_output_tokens(policies: Sequence[PolicyRecord]) -> int | None:
        token_limits = [
            int(policy.rule_value)
            for policy in policies
            if policy.rule_type == MAX_OUTPUT_TOKENS_RULE
        ]
        if not token_limits:
            return None
        return min(token_limits)

    @staticmethod
    def _rule_matches_model(policy: PolicyRecord, model: str) -> bool:
        return fnmatchcase(model, policy.rule_value)
