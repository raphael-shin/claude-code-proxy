from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import AppDependencies
from models.domain import UserRecord, VirtualKeyCacheEntry, VirtualKeyStatus
from proxy.model_resolver import ResolvedModel, ResolvedModelCapabilities
from proxy.policy_engine import PolicyDecision
from proxy.quota_engine import QuotaDecision
from proxy.rate_limiter import RateLimitDecision
from scripts.api_key_helper import ApiKeyHelper, CacheFileHelper
from tests.api.runtime_stubs import (
    AuthServiceStub,
    BedrockClientStub,
    PolicyEngineStub,
    QuotaEngineStub,
    RateLimiterStub,
    ResolverStub,
    build_authenticated_request_context,
)
from tests.fakes import (
    FakeClock,
    FakeEncryptionService,
    InMemoryUserRepository,
    InMemoryVirtualKeyCacheRepository,
    InMemoryVirtualKeyLedgerRepository,
)
from tests.perf.config import (
    FIRST_STREAM_EVENT_P95_MS,
    LOCAL_CACHE_HIT_MAX_MS,
    PERF_SAMPLE_SIZE,
    PERF_WARMUP_RUNS,
    TOKEN_SERVICE_CACHE_HIT_P95_MS,
)
from tests.perf.harness import run_probe
from token_service.handler import TokenServiceHandlerDependencies, handle_get_or_create_key
from token_service.issue_service import TokenIssueService


class SessionBootstrapperStub:
    def ensure_session(self) -> None:
        raise AssertionError("cached api key probe should not refresh the session")

    def export_credentials(self):  # pragma: no cover - defensive
        raise AssertionError("cached api key probe should not export credentials")


class TokenServiceClientStub:
    def get_or_create_key(self, credentials):  # pragma: no cover - defensive
        del credentials
        raise AssertionError("cached api key probe should not call the token service")


def test_perf_contract_local_cache_hit_returns_within_100ms(tmp_path: Path) -> None:
    now = datetime(2026, 3, 29, tzinfo=timezone.utc)
    cache = CacheFileHelper(path=tmp_path / "cache.json")
    cache.store(virtual_key="vk_cached_perf_1234567890", now=now, ttl_seconds=300)
    helper = ApiKeyHelper(
        cache=cache,
        session_bootstrapper=SessionBootstrapperStub(),
        token_service_client=TokenServiceClientStub(),
        clock=lambda: now,
    )

    probe, results = run_probe(
        helper.get_api_key,
        warmups=PERF_WARMUP_RUNS,
        sample_size=PERF_SAMPLE_SIZE,
    )

    assert all(result == "vk_cached_perf_1234567890" for result in results)
    assert probe.p95_ms < LOCAL_CACHE_HIT_MAX_MS


def test_perf_contract_token_service_cache_hit_p95_is_under_200ms() -> None:
    now = datetime(2026, 3, 29, tzinfo=timezone.utc)
    user_repository = InMemoryUserRepository()
    user_repository.add_user(
        UserRecord(id="user-1", email="dev@example.com", display_name="Dev"),
        username="alice",
    )
    encryption_service = FakeEncryptionService()
    cache_repository = InMemoryVirtualKeyCacheRepository()
    cache_repository.seed(
        VirtualKeyCacheEntry(
            user_id="user-1",
            virtual_key_id="vk-record-1",
            encrypted_key_ref=encryption_service.encrypt("vk_cached_perf_1234567890"),
            key_prefix="vk_cached",
            status=VirtualKeyStatus.ACTIVE,
            ttl=int((now + timedelta(minutes=15)).timestamp()),
        )
    )
    issue_service = TokenIssueService(
        user_repository=user_repository,
        virtual_key_repository=InMemoryVirtualKeyLedgerRepository(),
        virtual_key_cache=cache_repository,
        encryption_service=encryption_service,
        clock=FakeClock(now),
    )
    dependencies = TokenServiceHandlerDependencies(
        user_repository=user_repository,
        issue_service=issue_service,
        request_id_generator=lambda: "generated-request-id",
    )
    event = {
        "requestContext": {
            "requestId": "req-token-perf-1",
            "identity": {
                "userArn": "arn:aws:sts::123456789012:assumed-role/AWSReservedSSO_Dev/alice"
            },
        }
    }

    def invoke_handler() -> dict:
        return handle_get_or_create_key(event, dependencies=dependencies)

    probe, responses = run_probe(
        invoke_handler,
        warmups=PERF_WARMUP_RUNS,
        sample_size=PERF_SAMPLE_SIZE,
    )

    assert all(response["statusCode"] == 200 for response in responses)
    assert all(
        json.loads(response["body"])["virtual_key"] == "vk_cached_perf_1234567890"
        for response in responses
    )
    assert probe.p95_ms < TOKEN_SERVICE_CACHE_HIT_P95_MS


def test_perf_contract_streaming_first_event_p95_is_under_200ms() -> None:
    user = UserRecord(id="user-1", email="dev@example.com", display_name="Dev")
    app = create_app(
        AppDependencies(
            auth_service=AuthServiceStub(
                authenticated=build_authenticated_request_context(user)
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
            bedrock_client=BedrockClientStub(
                converse_stream_response=[
                    {"messageStart": {"role": "assistant"}},
                    {"contentBlockStart": {"contentBlockIndex": 0, "start": {"text": {}}}},
                    {"contentBlockDelta": {"contentBlockIndex": 0, "delta": {"text": "Hello"}}},
                    {"contentBlockStop": {"contentBlockIndex": 0}},
                    {"messageStop": {"stopReason": "end_turn"}},
                    {
                        "metadata": {
                            "usage": {
                                "inputTokens": 10,
                                "outputTokens": 20,
                                "totalTokens": 30,
                            }
                        }
                    },
                ]
            ),
            request_id_generator=lambda: "req-stream-perf-1",
        )
    )

    with TestClient(app) as client:
        def read_first_stream_event() -> str:
            with client.stream(
                "POST",
                "/v1/messages",
                headers={"Authorization": "Bearer vk_valid"},
                json={
                    "model": "claude-sonnet-4-5",
                    "stream": True,
                    "messages": [{"role": "user", "content": "hello"}],
                },
            ) as response:
                assert response.status_code == 200
                return next(response.iter_lines())

        probe, events = run_probe(
            read_first_stream_event,
            warmups=PERF_WARMUP_RUNS,
            sample_size=PERF_SAMPLE_SIZE,
        )

    assert all(event == "event: message_start" for event in events)
    assert probe.p95_ms < FIRST_STREAM_EVENT_P95_MS


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
