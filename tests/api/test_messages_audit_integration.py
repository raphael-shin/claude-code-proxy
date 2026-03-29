from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import AppDependencies
from models.domain import UserRecord
from proxy.audit_logger import AuditLogger
from proxy.model_resolver import ResolvedModel, ResolvedModelCapabilities
from proxy.policy_engine import DENIAL_MODEL_DENIED, PolicyDecision
from proxy.quota_engine import QuotaDecision, UsageCostSnapshot
from proxy.rate_limiter import RateLimitDecision
from tests.api.runtime_stubs import (
    AuthServiceStub,
    BedrockClientStub,
    PolicyEngineStub,
    QuotaEngineStub,
    RateLimiterStub,
    ResolverStub,
    build_authenticated_request_context,
)
from tests.fakes import FakeClock, InMemoryUsageRepository


def test_messages_success_records_usage_and_audit_after_response_mapping() -> None:
    repository = InMemoryUsageRepository()
    app = create_app(
        AppDependencies(
            auth_service=AuthServiceStub(
                authenticated=build_authenticated_request_context(_user())
            ),
            model_resolver=ResolverStub(_resolved_model()),
            policy_engine=PolicyEngineStub(PolicyDecision(allowed=True)),
            quota_engine=QuotaEngineStub(
                QuotaDecision(
                    allowed=True,
                    denial_reason=None,
                    effective_policy=None,
                    soft_limit_reached=False,
                    hard_limit_reached=False,
                    projected_usage=0.0,
                    usage_snapshot=_usage_snapshot(),
                )
            ),
            rate_limiter=RateLimiterStub(RateLimitDecision(allowed=True)),
            bedrock_client=BedrockClientStub(
                converse_response={
                    "output": {
                        "message": {
                            "role": "assistant",
                            "content": [{"text": "hello"}],
                        }
                    },
                    "stopReason": "end_turn",
                    "usage": {
                        "inputTokens": 11,
                        "outputTokens": 22,
                        "totalTokens": 33,
                        "cacheWriteInputTokens": 4,
                        "cacheReadInputTokens": 5,
                        "cacheDetails": {"ttl": "5m"},
                    },
                }
            ),
            audit_logger=AuditLogger(
                usage_repository=repository,
                clock=FakeClock(datetime(2026, 3, 29, tzinfo=timezone.utc)),
                event_id_generator=_event_id_generator(),
            ),
            request_id_generator=lambda: "req-audit-1",
        )
    )

    response = TestClient(app).post(
        "/v1/messages",
        headers={"Authorization": "Bearer vk_valid"},
        json={"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 200
    assert len(repository.usage_events) == 1
    assert len(repository.audit_events) == 1
    usage_event = repository.usage_events[0]
    assert usage_event.request_id == "req-audit-1"
    assert usage_event.total_tokens == 33
    assert usage_event.pricing_catalog_id == "price-1"
    assert usage_event.cache_write_input_tokens == 4
    assert usage_event.cache_read_input_tokens == 5


def test_messages_streaming_records_usage_and_audit_after_stream_completion() -> None:
    repository = InMemoryUsageRepository()
    app = create_app(
        AppDependencies(
            auth_service=AuthServiceStub(
                authenticated=build_authenticated_request_context(_user())
            ),
            model_resolver=ResolverStub(_resolved_model()),
            policy_engine=PolicyEngineStub(PolicyDecision(allowed=True)),
            quota_engine=QuotaEngineStub(
                QuotaDecision(
                    allowed=True,
                    denial_reason=None,
                    effective_policy=None,
                    soft_limit_reached=False,
                    hard_limit_reached=False,
                    projected_usage=0.0,
                    usage_snapshot=_usage_snapshot(),
                )
            ),
            rate_limiter=RateLimiterStub(RateLimitDecision(allowed=True)),
            bedrock_client=BedrockClientStub(
                converse_stream_response=[
                    {"messageStart": {"role": "assistant"}},
                    {"contentBlockStart": {"contentBlockIndex": 0, "start": {"text": {}}}},
                    {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "hello"}}},
                    {"contentBlockStop": {"contentBlockIndex": 0}},
                    {"messageStop": {"stopReason": "end_turn"}},
                    {
                        "metadata": {
                            "usage": {
                                "inputTokens": 7,
                                "outputTokens": 8,
                                "totalTokens": 9,
                            }
                        }
                    },
                ]
            ),
            audit_logger=AuditLogger(
                usage_repository=repository,
                clock=FakeClock(datetime(2026, 3, 29, tzinfo=timezone.utc)),
                event_id_generator=_event_id_generator(),
            ),
            request_id_generator=lambda: "req-audit-stream",
        )
    )

    with TestClient(app).stream(
        "POST",
        "/v1/messages",
        headers={"Authorization": "Bearer vk_valid"},
        json={
            "model": "claude-sonnet-4-5",
            "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
        },
    ) as response:
        list(response.iter_lines())

    assert response.status_code == 200
    assert len(repository.usage_events) == 1
    assert repository.usage_events[0].total_tokens == 9
    assert len(repository.audit_events) == 1


def test_messages_denial_records_audit_only_and_count_tokens_records_nothing() -> None:
    repository = InMemoryUsageRepository()
    app = create_app(
        AppDependencies(
            auth_service=AuthServiceStub(
                authenticated=build_authenticated_request_context(_user())
            ),
            model_resolver=ResolverStub(_resolved_model()),
            policy_engine=PolicyEngineStub(
                PolicyDecision(allowed=False, denial_reason=DENIAL_MODEL_DENIED)
            ),
            quota_engine=QuotaEngineStub(
                QuotaDecision(
                    allowed=True,
                    denial_reason=None,
                    effective_policy=None,
                    soft_limit_reached=False,
                    hard_limit_reached=False,
                    projected_usage=0.0,
                )
            ),
            rate_limiter=RateLimiterStub(RateLimitDecision(allowed=True)),
            bedrock_client=BedrockClientStub(count_tokens_response={"inputTokens": 77}),
            audit_logger=AuditLogger(
                usage_repository=repository,
                clock=FakeClock(datetime(2026, 3, 29, tzinfo=timezone.utc)),
                event_id_generator=_event_id_generator(),
            ),
            request_id_generator=lambda: "req-audit-deny",
        )
    )

    deny_response = TestClient(app).post(
        "/v1/messages",
        headers={"Authorization": "Bearer vk_valid"},
        json={"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "hi"}]},
    )
    count_response = TestClient(app).post(
        "/v1/messages/count_tokens",
        headers={"Authorization": "Bearer vk_valid"},
        json={"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert deny_response.status_code == 403
    assert count_response.status_code == 200
    assert len(repository.usage_events) == 0
    assert len(repository.audit_events) == 1
    assert repository.audit_events[0].decision == "denied"


def _user() -> UserRecord:
    return UserRecord(
        id="user-1",
        email="dev@example.com",
        display_name="Dev User",
        groups=("eng",),
        department="platform",
    )


def _resolved_model() -> ResolvedModel:
    return ResolvedModel(
        requested_model="claude-sonnet-4-5",
        logical_model="sonnet",
        provider="bedrock",
        bedrock_api_route="converse",
        bedrock_model_id="anthropic.claude-sonnet-4-5-v1:0",
        inference_profile_id=None,
        aws_region_name="us-east-1",
        capabilities=ResolvedModelCapabilities(
            supports_native_structured_output=True,
            supports_reasoning=True,
            supports_prompt_cache_ttl=True,
            supports_disable_parallel_tool_use=True,
        ),
    )


def _usage_snapshot() -> UsageCostSnapshot:
    return UsageCostSnapshot(
        pricing_catalog_id="price-1",
        estimated_input_cost_usd=0.001,
        estimated_output_cost_usd=0.002,
        estimated_cache_write_cost_usd=0.0001,
        estimated_cache_read_cost_usd=0.00005,
        estimated_total_cost_usd=0.00315,
    )


def _event_id_generator():
    counter = {"value": 0}

    def _next() -> str:
        counter["value"] += 1
        return f"event-{counter['value']}"

    return _next
