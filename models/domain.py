from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VirtualKeyStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    REVOKED = "revoked"


class TokenIssueSource(str, Enum):
    CACHE = "cache"
    REUSED = "reused"
    ISSUED = "issued"


class BudgetPeriodType(str, Enum):
    DAY = "day"
    MONTH = "month"


class BudgetMetricType(str, Enum):
    TOKENS = "tokens"
    COST_USD = "cost_usd"


@dataclass(frozen=True, slots=True)
class IdentityMapping:
    username: str
    user_id: str
    identity_provider: str = "identity-center"
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: str
    email: str
    display_name: str
    department: str | None = None
    cost_center: str | None = None
    groups: tuple[str, ...] = ()
    proxy_access_enabled: bool = True
    is_active: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        object.__setattr__(self, "groups", tuple(self.groups))


@dataclass(frozen=True, slots=True)
class VirtualKeyRecord:
    id: str
    user_id: str
    key_hash: str
    encrypted_key_blob: str
    key_prefix: str
    status: VirtualKeyStatus
    created_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class VirtualKeyCacheEntry:
    user_id: str
    virtual_key_id: str
    encrypted_key_ref: str
    key_prefix: str
    status: VirtualKeyStatus
    ttl: int


@dataclass(frozen=True, slots=True)
class AdminIdentityRecord:
    principal_id: str
    role: str
    is_active: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class TokenIssueResult:
    virtual_key: str
    user_id: str
    key_id: str
    key_prefix: str
    status: VirtualKeyStatus
    source: TokenIssueSource
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PolicyRecord:
    id: str
    scope_type: str
    scope_id: str
    rule_type: str
    rule_value: str
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class BudgetPolicyRecord:
    id: str
    scope_type: str
    scope_id: str
    period_type: BudgetPeriodType
    metric_type: BudgetMetricType
    limit_value: int
    soft_limit_percent: int
    hard_limit_percent: int
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class ModelAliasRuleRecord:
    id: str
    pattern: str
    logical_model: str
    priority: int
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class ModelRouteRecord:
    id: str
    logical_model: str
    provider: str
    bedrock_api_route: str
    bedrock_model_id: str | None
    inference_profile_id: str | None
    supports_native_structured_output: bool
    supports_reasoning: bool
    supports_prompt_cache_ttl: bool
    supports_disable_parallel_tool_use: bool
    priority: int
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class ModelPricingRecord:
    id: str
    provider: str
    model_id: str
    input_cost_per_million: float
    output_cost_per_million: float
    cache_write_input_cost_per_million: float = 0.0
    cache_read_input_cost_per_million: float = 0.0
    currency: str = "USD"
    effective_from: date | None = None
    effective_to: date | None = None


@dataclass(frozen=True, slots=True)
class UsageEventRecord:
    id: str
    request_id: str
    user_id: str
    user_email: str | None
    requested_model: str
    resolved_model: str | None
    pricing_catalog_id: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cache_write_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_details: dict[str, Any] | None = None
    estimated_input_cost_usd: float = 0.0
    estimated_output_cost_usd: float = 0.0
    estimated_cache_write_cost_usd: float = 0.0
    estimated_cache_read_cost_usd: float = 0.0
    estimated_total_cost_usd: float = 0.0
    latency_ms: int | None = None
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True, slots=True)
class AuditEventRecord:
    id: str
    request_id: str
    event_type: str
    actor_user_id: str | None
    actor_user_email: str | None
    decision: str
    requested_model: str | None = None
    resolved_model: str | None = None
    denial_reason: str | None = None
    policy_result: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=utc_now)
