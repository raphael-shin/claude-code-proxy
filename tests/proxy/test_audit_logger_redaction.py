from __future__ import annotations

from datetime import datetime, timezone

from models.domain import UserRecord
from proxy.audit_logger import AuditLogger
from proxy.policy_engine import PolicyDecision
from proxy.quota_engine import UsageCostSnapshot
from tests.api.runtime_stubs import build_authenticated_request_context
from tests.fakes import FakeClock, InMemoryUsageRepository


def test_audit_logger_records_usage_without_prompt_or_plaintext_key() -> None:
    user = UserRecord(
        id="user-1",
        email="dev@example.com",
        display_name="Dev User",
        groups=("eng",),
        department="platform",
    )
    repository = InMemoryUsageRepository()
    clock = FakeClock(datetime(2026, 3, 29, tzinfo=timezone.utc))
    event_ids = iter(("usage-1", "audit-1"))
    audit_logger = AuditLogger(
        usage_repository=repository,
        clock=clock,
        event_id_generator=lambda: next(event_ids),
    )

    audit_logger.record_success(
        authenticated=build_authenticated_request_context(user),
        request_id="req-usage-1",
        requested_model="claude-sonnet-4-5",
        resolved_model="anthropic.claude-sonnet-4-5-v1:0",
        policy_decision=PolicyDecision(allowed=True, effective_max_output_tokens=2048),
        usage={
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 120,
            "cache_write_input_tokens": 10,
            "cache_read_input_tokens": 5,
            "cache_details": {"ttl": "5m"},
        },
        usage_snapshot=UsageCostSnapshot(
            pricing_catalog_id="price-1",
            estimated_input_cost_usd=0.001,
            estimated_output_cost_usd=0.002,
            estimated_cache_write_cost_usd=0.0001,
            estimated_cache_read_cost_usd=0.00005,
            estimated_total_cost_usd=0.00315,
        ),
        latency_ms=87,
    )

    usage_event = repository.usage_events[0]
    audit_event = repository.audit_events[0]

    assert usage_event.request_id == "req-usage-1"
    assert usage_event.pricing_catalog_id == "price-1"
    assert usage_event.total_tokens == 120
    assert usage_event.cache_write_input_tokens == 10
    assert usage_event.cache_read_input_tokens == 5
    assert usage_event.cache_details == {"ttl": "5m"}
    assert usage_event.estimated_cache_write_cost_usd == 0.0001
    assert usage_event.estimated_cache_read_cost_usd == 0.00005
    assert usage_event.estimated_total_cost_usd == 0.00315
    assert usage_event.latency_ms == 87
    assert not hasattr(usage_event, "prompt")
    assert not hasattr(usage_event, "virtual_key")

    assert audit_event.request_id == "req-usage-1"
    assert audit_event.decision == "allowed"
    assert audit_event.requested_model == "claude-sonnet-4-5"
    assert audit_event.resolved_model == "anthropic.claude-sonnet-4-5-v1:0"
    assert audit_event.policy_result is not None
    assert audit_event.policy_result["allowed"] is True
    assert not hasattr(audit_event, "prompt")
    assert not hasattr(audit_event, "virtual_key")
