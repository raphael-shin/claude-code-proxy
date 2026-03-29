from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import AppDependencies
from api.observability import (
    REQUEST_ID_HEADER,
    RUNTIME_LOGGER_NAME,
    RUNTIME_REQUEST_COUNT_METRIC,
    RUNTIME_REQUEST_ERROR_COUNT_METRIC,
    RUNTIME_REQUEST_LATENCY_METRIC,
)
from models.domain import TokenIssueResult, TokenIssueSource, UserRecord, VirtualKeyStatus
from models.errors import authentication_failed_error
from proxy.model_resolver import ResolvedModel, ResolvedModelCapabilities
from proxy.policy_engine import PolicyDecision
from proxy.quota_engine import QuotaDecision
from proxy.rate_limiter import RateLimitDecision
from tests.api.runtime_stubs import (
    AuthServiceStub,
    BedrockClientStub,
    PolicyEngineStub,
    QuotaEngineStub,
    RateLimiterStub,
    ResolverStub,
)
from tests.fakes import FakeRequestIdGenerator, InMemoryUserRepository
from token_service.handler import (
    TOKEN_SERVICE_CACHE_HIT_METRIC,
    TOKEN_SERVICE_ERROR_COUNT_METRIC,
    TOKEN_SERVICE_LATENCY_METRIC,
    TOKEN_SERVICE_LOGGER_NAME,
    TOKEN_SERVICE_REQUEST_COUNT_METRIC,
    TokenServiceHandlerDependencies,
    handle_get_or_create_key,
)


class MetricsRecorder:
    def __init__(self) -> None:
        self.counters: list[dict[str, object]] = []
        self.observations: list[dict[str, object]] = []

    def increment(self, name: str, *, value: int = 1, tags=None) -> None:
        self.counters.append({"name": name, "value": value, "tags": dict(tags or {})})

    def observe(self, name: str, value: float, *, tags=None) -> None:
        self.observations.append({"name": name, "value": value, "tags": dict(tags or {})})


class DummyIssueService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def get_or_create_key(self, user_id: str, *, request_id: str) -> None:
        self.calls.append((user_id, request_id))
        raise AssertionError("issue service should not be called for an unregistered user")


class CacheHitIssueService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def get_or_create_key(self, user_id: str, *, request_id: str) -> TokenIssueResult:
        self.calls.append((user_id, request_id))
        return TokenIssueResult(
            virtual_key="vk_cached_1234567890",
            user_id=user_id,
            key_id="vk-record-1",
            key_prefix="vk_cached",
            status=VirtualKeyStatus.ACTIVE,
            source=TokenIssueSource.CACHE,
        )


def test_runtime_failure_logs_request_id_and_records_metrics(caplog) -> None:
    metrics = MetricsRecorder()
    app = create_app(
        AppDependencies(
            auth_service=AuthServiceStub(
                error=authentication_failed_error(
                    "req-runtime-metric-1",
                    details={"reason": "missing_bearer_token"},
                )
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
                )
            ),
            rate_limiter=RateLimiterStub(RateLimitDecision(allowed=True)),
            bedrock_client=BedrockClientStub(),
            runtime_metrics=metrics,
            request_id_generator=lambda: "req-runtime-metric-1",
        )
    )

    with caplog.at_level(logging.WARNING, logger=RUNTIME_LOGGER_NAME):
        response = TestClient(app).post(
            "/v1/messages",
            json={"model": "claude-sonnet-4-5", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert response.status_code == 401
    assert response.headers[REQUEST_ID_HEADER] == "req-runtime-metric-1"
    assert _metric_names(metrics.counters) == [
        RUNTIME_REQUEST_COUNT_METRIC,
        RUNTIME_REQUEST_ERROR_COUNT_METRIC,
    ]
    assert _metric_names(metrics.observations) == [RUNTIME_REQUEST_LATENCY_METRIC]

    log_payload = json.loads(caplog.records[-1].getMessage())
    assert log_payload["request_id"] == "req-runtime-metric-1"
    assert log_payload["path"] == "/v1/messages"
    assert log_payload["status_code"] == 401


def test_token_service_failure_logs_request_id_and_records_metrics(caplog) -> None:
    metrics = MetricsRecorder()
    dependencies = TokenServiceHandlerDependencies(
        user_repository=InMemoryUserRepository(),
        issue_service=DummyIssueService(),
        request_id_generator=FakeRequestIdGenerator("req-token-observe-1"),
        metrics=metrics,
    )

    with caplog.at_level(logging.WARNING, logger=TOKEN_SERVICE_LOGGER_NAME):
        response = handle_get_or_create_key(
            {
                "requestContext": {
                    "identity": {
                        "userArn": (
                            "arn:aws:sts::123456789012:assumed-role/"
                            "AWSReservedSSO_Dev/alice"
                        )
                    }
                }
            },
            dependencies=dependencies,
        )

    body = json.loads(response["body"])
    assert response["statusCode"] == 403
    assert _metric_names(metrics.counters) == [
        TOKEN_SERVICE_REQUEST_COUNT_METRIC,
        TOKEN_SERVICE_ERROR_COUNT_METRIC,
    ]
    assert _metric_names(metrics.observations) == [TOKEN_SERVICE_LATENCY_METRIC]

    log_payload = json.loads(caplog.records[-1].getMessage())
    assert log_payload["request_id"] == "req-token-observe-1"
    assert log_payload["status_code"] == 403
    assert log_payload["error_type"] == body["error"]["type"]


def test_token_service_cache_hit_records_cache_metric() -> None:
    metrics = MetricsRecorder()
    user_repository = InMemoryUserRepository()
    user_repository.add_user(
        UserRecord(id="user-1", email="dev@example.com", display_name="Dev"),
        username="alice",
    )
    dependencies = TokenServiceHandlerDependencies(
        user_repository=user_repository,
        issue_service=CacheHitIssueService(),
        request_id_generator=FakeRequestIdGenerator("req-token-cache-hit"),
        metrics=metrics,
    )

    response = handle_get_or_create_key(
        {
            "requestContext": {
                "identity": {
                    "userArn": "arn:aws:sts::123456789012:assumed-role/AWSReservedSSO_Dev/alice"
                }
            }
        },
        dependencies=dependencies,
    )

    assert response["statusCode"] == 200
    assert _metric_names(metrics.counters) == [
        TOKEN_SERVICE_REQUEST_COUNT_METRIC,
        TOKEN_SERVICE_CACHE_HIT_METRIC,
    ]


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


def _metric_names(records: list[dict[str, object]]) -> list[str]:
    return [str(record["name"]) for record in records]
