from __future__ import annotations

from collections.abc import Sequence

from models.domain import (
    AuditEventRecord,
    BudgetPolicyRecord,
    IdentityMapping,
    ModelPricingRecord,
    ModelRouteRecord,
    UsageEventRecord,
    UserRecord,
    VirtualKeyRecord,
)


class InMemoryAdminIdentityRepository:
    def __init__(self, roles: dict[str, str] | None = None) -> None:
        self._roles = dict(roles or {})

    def get_admin_role(self, principal_id: str) -> str | None:
        return self._roles.get(principal_id)


class InMemoryUserProvisioningStore:
    def __init__(self) -> None:
        self.users: dict[str, UserRecord] = {}
        self.mappings: dict[str, IdentityMapping] = {}

    def provision_user(self, *, user: UserRecord, mapping: IdentityMapping) -> None:
        self.users[user.id] = user
        self.mappings[mapping.username] = mapping


class ProvisionedUserRepository:
    def __init__(self, store: InMemoryUserProvisioningStore) -> None:
        self._store = store

    def get_user_id_for_username(self, username: str) -> str | None:
        mapping = self._store.mappings.get(username)
        return None if mapping is None else mapping.user_id

    def get_user(self, user_id: str) -> UserRecord | None:
        return self._store.users.get(user_id)


class InMemoryBudgetPolicyStore:
    def __init__(self) -> None:
        self.saved_policies: list[BudgetPolicyRecord] = []

    def create_policy(self, policy: BudgetPolicyRecord) -> None:
        self.saved_policies.append(policy)


class InMemoryVirtualKeyAdminRepository:
    def __init__(self) -> None:
        self.records: dict[str, VirtualKeyRecord] = {}

    def seed(self, record: VirtualKeyRecord) -> None:
        self.records[record.id] = record

    def get_key(self, key_id: str) -> VirtualKeyRecord | None:
        return self.records.get(key_id)

    def get_key_by_hash(self, key_hash: str) -> VirtualKeyRecord | None:
        for record in self.records.values():
            if record.key_hash == key_hash:
                return record
        return None

    def save_key(self, record: VirtualKeyRecord) -> None:
        self.records[record.id] = record


class TrackingInvalidationDispatcher:
    def __init__(self) -> None:
        self.token_service_invalidations: list[str] = []
        self.proxy_auth_invalidations: list[str] = []

    def invalidate_token_service_cache(self, user_id: str) -> None:
        self.token_service_invalidations.append(user_id)

    def invalidate_proxy_auth_cache(self, key_id: str) -> None:
        self.proxy_auth_invalidations.append(key_id)


class InMemoryModelRouteStore:
    def __init__(self) -> None:
        self.records: dict[str, ModelRouteRecord] = {}

    def upsert_model_route(self, record: ModelRouteRecord) -> None:
        self.records[record.id] = record


class InMemoryPricingStore:
    def __init__(self) -> None:
        self.records: dict[str, ModelPricingRecord] = {}

    def upsert_pricing(self, record: ModelPricingRecord) -> None:
        self.records[record.id] = record


class ReloadNotifier:
    def __init__(self) -> None:
        self.reload_calls = 0

    def reload(self) -> None:
        self.reload_calls += 1


class InMemoryUsageQueryService:
    def __init__(
        self,
        *,
        usage_events: Sequence[UsageEventRecord] = (),
        audit_events: Sequence[AuditEventRecord] = (),
    ) -> None:
        self._usage_events = list(usage_events)
        self._audit_events = list(audit_events)

    def query_usage(
        self,
        *,
        user_id: str | None = None,
        team_id: str | None = None,
        model: str | None = None,
    ) -> list[UsageEventRecord]:
        items = list(self._usage_events)
        if user_id is not None:
            items = [item for item in items if item.user_id == user_id]
        if team_id is not None:
            items = [item for item in items if item.team_id == team_id]
        if model is not None:
            items = [item for item in items if item.requested_model == model]
        return items

    def query_audit_events(
        self,
        *,
        user_id: str | None = None,
        team_id: str | None = None,
        model: str | None = None,
        event_type: str | None = None,
    ) -> list[AuditEventRecord]:
        items = list(self._audit_events)
        if user_id is not None:
            items = [item for item in items if item.actor_user_id == user_id]
        if team_id is not None:
            items = [item for item in items if item.team_id == team_id]
        if model is not None:
            items = [
                item
                for item in items
                if item.requested_model == model or item.resolved_model == model
            ]
        if event_type is not None:
            items = [item for item in items if item.event_type == event_type]
        return items


def admin_headers(principal_id: str) -> dict[str, str]:
    return {"X-Admin-Principal": principal_id}
