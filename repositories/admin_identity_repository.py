from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from models.domain import AdminIdentityRecord


@runtime_checkable
class AdminIdentityStore(Protocol):
    def get_admin_identity(self, principal_id: str) -> AdminIdentityRecord | None: ...


class PostgresAdminIdentityRepository:
    def __init__(self, store: AdminIdentityStore) -> None:
        self._store = store

    def get_admin_role(self, principal_id: str) -> str | None:
        identity = self._store.get_admin_identity(principal_id)
        if identity is None or not identity.is_active:
            return None
        return identity.role


class PsycopgAdminIdentityStore:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def get_admin_identity(self, principal_id: str) -> AdminIdentityRecord | None:
        row = self._connection.execute(
            """
            SELECT principal_id, role, is_active, created_at, updated_at
            FROM admin_identities
            WHERE principal_id = %(principal_id)s
            """,
            {"principal_id": principal_id},
        ).fetchone()
        if row is None:
            return None
        return AdminIdentityRecord(
            principal_id=row["principal_id"],
            role=row["role"],
            is_active=row["is_active"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@runtime_checkable
class AdminIdentityRepository(Protocol):
    def get_admin_role(self, principal_id: str) -> str | None: ...
