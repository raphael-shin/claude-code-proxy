from __future__ import annotations

from datetime import datetime

from models.domain import (
    IdentityMapping,
    ModelAliasRuleRecord,
    ModelRouteRecord,
    UserRecord,
    VirtualKeyCacheEntry,
    VirtualKeyRecord,
    VirtualKeyStatus,
)


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._users: dict[str, UserRecord] = {}
        self._mappings: dict[str, str] = {}
        self.get_user_id_calls: list[str] = []
        self.get_user_calls: list[str] = []

    def add_user(self, user: UserRecord, *, username: str | None = None) -> None:
        self._users[user.id] = user
        if username is not None:
            self._mappings[username] = user.id

    def get_user_id_for_username(self, username: str) -> str | None:
        self.get_user_id_calls.append(username)
        return self._mappings.get(username)

    def get_user(self, user_id: str) -> UserRecord | None:
        self.get_user_calls.append(user_id)
        return self._users.get(user_id)


class InMemoryVirtualKeyLedgerRepository:
    def __init__(self) -> None:
        self._records: dict[str, VirtualKeyRecord] = {}
        self.get_active_key_calls: list[str] = []
        self.saved_records: list[VirtualKeyRecord] = []

    def seed(self, record: VirtualKeyRecord) -> None:
        self._records[record.id] = record

    def get_active_key_for_user(self, user_id: str) -> VirtualKeyRecord | None:
        self.get_active_key_calls.append(user_id)
        active_records = [
            record
            for record in self._records.values()
            if record.user_id == user_id and record.status == VirtualKeyStatus.ACTIVE
        ]
        if not active_records:
            return None
        return max(active_records, key=lambda record: record.created_at)

    def save_key(self, record: VirtualKeyRecord) -> None:
        self.saved_records.append(record)
        self._records[record.id] = record


class InMemoryVirtualKeyCacheRepository:
    def __init__(self) -> None:
        self._entries: dict[str, VirtualKeyCacheEntry] = {}
        self.get_active_key_calls: list[str] = []
        self.saved_entries: list[VirtualKeyCacheEntry] = []
        self.invalidated_user_ids: list[str] = []

    @property
    def entries(self) -> dict[str, VirtualKeyCacheEntry]:
        return dict(self._entries)

    def seed(self, entry: VirtualKeyCacheEntry) -> None:
        self._entries[entry.user_id] = entry

    def get_active_key(self, user_id: str, now: datetime) -> VirtualKeyCacheEntry | None:
        self.get_active_key_calls.append(user_id)
        entry = self._entries.get(user_id)
        if entry is None:
            return None
        if entry.ttl <= int(now.timestamp()):
            return None
        if entry.status != VirtualKeyStatus.ACTIVE:
            return None
        return entry

    def put_active_key(self, entry: VirtualKeyCacheEntry) -> None:
        self.saved_entries.append(entry)
        self._entries[entry.user_id] = entry

    def invalidate_user(self, user_id: str) -> None:
        self.invalidated_user_ids.append(user_id)
        self._entries.pop(user_id, None)


class InMemoryModelAliasRepository:
    def __init__(self, rules: list[ModelAliasRuleRecord] | None = None) -> None:
        self._rules = list(rules or [])
        self.list_alias_rules_calls = 0

    def add_rule(self, rule: ModelAliasRuleRecord) -> None:
        self._rules.append(rule)

    def list_alias_rules(self) -> list[ModelAliasRuleRecord]:
        self.list_alias_rules_calls += 1
        return list(self._rules)


class InMemoryModelRouteRepository:
    def __init__(self, routes: list[ModelRouteRecord] | None = None) -> None:
        self._routes = list(routes or [])
        self.list_model_routes_calls = 0

    def add_route(self, route: ModelRouteRecord) -> None:
        self._routes.append(route)

    def list_model_routes(self) -> list[ModelRouteRecord]:
        self.list_model_routes_calls += 1
        return list(self._routes)
