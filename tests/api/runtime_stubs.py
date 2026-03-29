from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models.context import AuthenticatedRequestContext, RequestContext, UserContext
from models.domain import UserRecord
from models.errors import ServiceError
from proxy.model_resolver import ResolvedModel
from proxy.policy_engine import PolicyDecision
from proxy.quota_engine import QuotaDecision
from proxy.rate_limiter import RateLimitDecision


def build_authenticated_request_context(user: UserRecord) -> AuthenticatedRequestContext:
    return AuthenticatedRequestContext(
        request=RequestContext(
            request_id="ignored",
            user=UserContext(
                user_id=user.id,
                email=user.email,
                groups=user.groups,
                department=user.department,
            ),
        ),
        user_record=user,
        virtual_key_id="vk-record-123",
        key_hash="key-hash",
        key_prefix="vk_prefix",
    )


class AuthServiceStub:
    def __init__(
        self,
        *,
        authenticated: AuthenticatedRequestContext | None = None,
        error: ServiceError | None = None,
        call_log: list[str] | None = None,
    ) -> None:
        self.authenticated = authenticated
        self.error = error
        self.call_log = call_log if call_log is not None else []
        self.calls: list[dict[str, Any]] = []

    def authenticate(self, authorization_header, *, request_id, headers=None, body=None):
        self.call_log.append("auth")
        self.calls.append(
            {
                "authorization_header": authorization_header,
                "request_id": request_id,
                "headers": headers,
                "body": body,
            }
        )
        if self.error is not None:
            raise self.error
        assert self.authenticated is not None
        return self.authenticated


class ResolverStub:
    def __init__(self, resolved_model: ResolvedModel, *, call_log: list[str] | None = None) -> None:
        self.resolved_model = resolved_model
        self.call_log = call_log if call_log is not None else []
        self.calls: list[str] = []

    def resolve(self, requested_model: str) -> ResolvedModel:
        self.call_log.append("resolve")
        self.calls.append(requested_model)
        return self.resolved_model


class PolicyEngineStub:
    def __init__(self, decision: PolicyDecision, *, call_log: list[str] | None = None) -> None:
        self.decision = decision
        self.call_log = call_log if call_log is not None else []
        self.calls: list[dict[str, Any]] = []

    def evaluate(self, *, user, model, policies):
        self.call_log.append("policy")
        self.calls.append({"user": user, "model": model, "policies": policies})
        return self.decision


class QuotaEngineStub:
    def __init__(self, decision: QuotaDecision, *, call_log: list[str] | None = None) -> None:
        self.decision = decision
        self.call_log = call_log if call_log is not None else []
        self.calls: list[dict[str, Any]] = []

    def evaluate(self, **kwargs):
        self.call_log.append("quota")
        self.calls.append(kwargs)
        return self.decision


class RateLimiterStub:
    def __init__(self, decision: RateLimitDecision, *, call_log: list[str] | None = None) -> None:
        self.decision = decision
        self.call_log = call_log if call_log is not None else []
        self.calls: list[str] = []

    def check(self, user_id: str) -> RateLimitDecision:
        self.call_log.append("rate_limit")
        self.calls.append(user_id)
        return self.decision


class BedrockClientStub:
    def __init__(
        self,
        *,
        converse_response: dict[str, Any] | None = None,
        converse_stream_response: list[dict[str, Any]] | None = None,
        count_tokens_response: dict[str, Any] | None = None,
        call_log: list[str] | None = None,
    ) -> None:
        self.converse_response = converse_response or {}
        self.converse_stream_response = list(converse_stream_response or [])
        self.count_tokens_response = count_tokens_response or {}
        self.call_log = call_log if call_log is not None else []
        self.converse_calls: list[Any] = []
        self.converse_stream_calls: list[Any] = []
        self.count_tokens_calls: list[Any] = []
        self.stream_events_yielded = 0

    def converse(self, converse_request):
        self.call_log.append("bedrock")
        self.converse_calls.append(converse_request)
        return self.converse_response

    def converse_stream(self, converse_request):
        self.call_log.append("bedrock")
        self.converse_stream_calls.append(converse_request)

        def _iterate():
            for event in self.converse_stream_response:
                self.stream_events_yielded += 1
                yield event

        return _iterate()

    def count_tokens(self, converse_request):
        self.call_log.append("count_tokens")
        self.count_tokens_calls.append(converse_request)
        return self.count_tokens_response


@dataclass(frozen=True, slots=True)
class ReadyCheck:
    value: bool

    def __call__(self) -> bool:
        return self.value
