from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from models.domain import IdentityMapping, UserRecord


@runtime_checkable
class UserRepository(Protocol):
    def get_user_id_for_username(self, username: str) -> str | None: ...

    def get_user(self, user_id: str) -> UserRecord | None: ...


class PostgresUserStore(Protocol):
    def get_identity_mapping(self, username: str) -> IdentityMapping | None: ...

    def get_user(self, user_id: str) -> UserRecord | None: ...


class PostgresUserRepository:
    def __init__(self, store: PostgresUserStore) -> None:
        self._store = store

    def get_user_id_for_username(self, username: str) -> str | None:
        mapping = self._store.get_identity_mapping(username)
        if mapping is None:
            return None
        return mapping.user_id

    def get_user(self, user_id: str) -> UserRecord | None:
        return self._store.get_user(user_id)


class PsycopgUserStore:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def get_identity_mapping(self, username: str) -> IdentityMapping | None:
        row = self._connection.execute(
            """
            SELECT username, user_id, identity_provider, created_at
            FROM identity_user_mappings
            WHERE username = %(username)s
            """,
            {"username": username},
        ).fetchone()
        if row is None:
            return None
        return IdentityMapping(
            username=row["username"],
            user_id=row["user_id"],
            identity_provider=row["identity_provider"],
            created_at=row["created_at"],
        )

    def get_user(self, user_id: str) -> UserRecord | None:
        row = self._connection.execute(
            """
            SELECT id, email, display_name, department, cost_center, groups,
                   proxy_access_enabled, is_active, created_at, updated_at
            FROM users
            WHERE id = %(user_id)s
            """,
            {"user_id": user_id},
        ).fetchone()
        if row is None:
            return None
        return UserRecord(
            id=row["id"],
            email=row["email"],
            display_name=row["display_name"],
            department=row["department"],
            cost_center=row["cost_center"],
            groups=tuple(row["groups"] or ()),
            proxy_access_enabled=row["proxy_access_enabled"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
