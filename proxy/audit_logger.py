from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Callable, Mapping
from uuid import uuid4

from models.context import AuthenticatedRequestContext
from models.domain import AuditEventRecord, UsageEventRecord
from proxy.policy_engine import PolicyDecision
from proxy.quota_engine import UsageCostSnapshot
from repositories.usage_repository import UsageRepository

Clock = Callable[[], datetime]
EventIdGenerator = Callable[[], str]

AUDIT_EVENT_AUTH_SUCCESS = "auth_success"
AUDIT_EVENT_AUTH_FAILURE = "auth_failure"
AUDIT_EVENT_POLICY_DENIED = "policy_denied"
AUDIT_EVENT_QUOTA_BLOCKED = "quota_hard_limit_blocked"
AUDIT_EVENT_RATE_LIMITED = "rate_limited"

AUDIT_DECISION_ALLOWED = "allowed"
AUDIT_DECISION_DENIED = "denied"

DENIAL_REASON_AUTHENTICATION_FAILED = "authentication_failed"
DENIAL_REASON_RATE_LIMITED = "rate_limited"


class AuditLogger:
    def __init__(
        self,
        *,
        usage_repository: UsageRepository,
        clock: Clock,
        event_id_generator: EventIdGenerator | None = None,
    ) -> None:
        self._usage_repository = usage_repository
        self._clock = clock
        self._event_id_generator = event_id_generator or (lambda: str(uuid4()))

    def record_success(
        self,
        *,
        authenticated: AuthenticatedRequestContext,
        request_id: str,
        requested_model: str,
        resolved_model: str | None,
        policy_decision: PolicyDecision,
        usage: Mapping[str, Any],
        usage_snapshot: UsageCostSnapshot | None,
        latency_ms: int | None = None,
    ) -> None:
        created_at = self._clock()
        usage_event = UsageEventRecord(
            id=self._event_id_generator(),
            request_id=request_id,
            user_id=authenticated.user.user_id,
            user_email=authenticated.user.email,
            requested_model=requested_model,
            resolved_model=resolved_model,
            pricing_catalog_id=usage_snapshot.pricing_catalog_id if usage_snapshot else None,
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            total_tokens=int(usage.get("total_tokens", 0) or 0),
            cache_write_input_tokens=int(usage.get("cache_write_input_tokens", 0) or 0),
            cache_read_input_tokens=int(usage.get("cache_read_input_tokens", 0) or 0),
            cache_details=usage.get("cache_details"),
            estimated_input_cost_usd=usage_snapshot.estimated_input_cost_usd if usage_snapshot else 0.0,
            estimated_output_cost_usd=usage_snapshot.estimated_output_cost_usd if usage_snapshot else 0.0,
            estimated_cache_write_cost_usd=(
                usage_snapshot.estimated_cache_write_cost_usd if usage_snapshot else 0.0
            ),
            estimated_cache_read_cost_usd=(
                usage_snapshot.estimated_cache_read_cost_usd if usage_snapshot else 0.0
            ),
            estimated_total_cost_usd=usage_snapshot.estimated_total_cost_usd if usage_snapshot else 0.0,
            latency_ms=latency_ms,
            created_at=created_at,
        )
        audit_event = AuditEventRecord(
            id=self._event_id_generator(),
            request_id=request_id,
            event_type=AUDIT_EVENT_AUTH_SUCCESS,
            actor_user_id=authenticated.user.user_id,
            actor_user_email=authenticated.user.email,
            decision=AUDIT_DECISION_ALLOWED,
            requested_model=requested_model,
            resolved_model=resolved_model,
            policy_result=self._policy_result_payload(policy_decision),
            created_at=created_at,
        )
        self._usage_repository.record_usage(usage_event)
        self._usage_repository.record_audit(audit_event)

    def record_denial(
        self,
        *,
        request_id: str,
        denial_reason: str,
        authenticated: AuthenticatedRequestContext | None = None,
        requested_model: str | None = None,
        resolved_model: str | None = None,
        policy_decision: PolicyDecision | None = None,
    ) -> None:
        event_type = _denial_reason_to_event_type(denial_reason)
        self._usage_repository.record_audit(
            AuditEventRecord(
                id=self._event_id_generator(),
                request_id=request_id,
                event_type=event_type,
                actor_user_id=authenticated.user.user_id if authenticated else None,
                actor_user_email=authenticated.user.email if authenticated else None,
                decision=AUDIT_DECISION_DENIED,
                requested_model=requested_model,
                resolved_model=resolved_model,
                denial_reason=denial_reason,
                policy_result=self._policy_result_payload(policy_decision) if policy_decision else None,
                created_at=self._clock(),
            )
        )

    @staticmethod
    def _policy_result_payload(policy_decision: PolicyDecision) -> dict[str, Any]:
        return {
            "allowed": policy_decision.allowed,
            "denial_reason": policy_decision.denial_reason,
            "effective_max_output_tokens": policy_decision.effective_max_output_tokens,
            "trace": asdict(policy_decision.trace),
        }


_DENIAL_REASON_TO_EVENT_TYPE = {
    "quota_hard_limit_exceeded": AUDIT_EVENT_QUOTA_BLOCKED,
    DENIAL_REASON_RATE_LIMITED: AUDIT_EVENT_RATE_LIMITED,
    DENIAL_REASON_AUTHENTICATION_FAILED: AUDIT_EVENT_AUTH_FAILURE,
}


def _denial_reason_to_event_type(denial_reason: str) -> str:
    return _DENIAL_REASON_TO_EVENT_TYPE.get(denial_reason, AUDIT_EVENT_POLICY_DENIED)
