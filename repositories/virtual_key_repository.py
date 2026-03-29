from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from models.domain import VirtualKeyCacheEntry, VirtualKeyRecord, VirtualKeyStatus


@runtime_checkable
class VirtualKeyLedgerRepository(Protocol):
    def get_active_key_for_user(self, user_id: str) -> VirtualKeyRecord | None: ...

    def save_key(self, record: VirtualKeyRecord) -> None: ...


@runtime_checkable
class VirtualKeyCacheRepository(Protocol):
    def get_active_key(self, user_id: str, now: datetime) -> VirtualKeyCacheEntry | None: ...

    def put_active_key(self, entry: VirtualKeyCacheEntry) -> None: ...

    def invalidate_user(self, user_id: str) -> None: ...


class PostgresVirtualKeyStore(Protocol):
    def list_virtual_keys_for_user(self, user_id: str) -> Sequence[VirtualKeyRecord]: ...

    def save_virtual_key(self, record: VirtualKeyRecord) -> None: ...


class DynamoDbTable(Protocol):
    def get_item(self, user_id: str) -> Mapping[str, Any] | None: ...

    def put_item(self, item: Mapping[str, Any]) -> None: ...

    def delete_item(self, user_id: str) -> None: ...


class PostgresVirtualKeyRepository:
    def __init__(self, store: PostgresVirtualKeyStore) -> None:
        self._store = store

    def get_active_key_for_user(self, user_id: str) -> VirtualKeyRecord | None:
        active_keys = [
            record
            for record in self._store.list_virtual_keys_for_user(user_id)
            if record.status == VirtualKeyStatus.ACTIVE
        ]
        if not active_keys:
            return None
        return max(active_keys, key=lambda record: record.created_at)

    def save_key(self, record: VirtualKeyRecord) -> None:
        self._store.save_virtual_key(record)


class PsycopgVirtualKeyStore:
    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def list_virtual_keys_for_user(self, user_id: str) -> Sequence[VirtualKeyRecord]:
        rows = self._connection.execute(
            """
            SELECT id, user_id, key_hash, encrypted_key_blob, key_prefix, status,
                   created_at, expires_at, revoked_at, last_used_at
            FROM virtual_keys
            WHERE user_id = %(user_id)s
            ORDER BY created_at DESC
            """,
            {"user_id": user_id},
        ).fetchall()
        return [
            VirtualKeyRecord(
                id=str(row["id"]),
                user_id=row["user_id"],
                key_hash=row["key_hash"],
                encrypted_key_blob=bytes(row["encrypted_key_blob"]).decode("utf-8"),
                key_prefix=row["key_prefix"],
                status=VirtualKeyStatus(row["status"]),
                created_at=row["created_at"],
                expires_at=row["expires_at"],
                revoked_at=row["revoked_at"],
                last_used_at=row["last_used_at"],
            )
            for row in rows
        ]

    def save_virtual_key(self, record: VirtualKeyRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO virtual_keys (
                id,
                key_hash,
                encrypted_key_blob,
                key_prefix,
                user_id,
                status,
                created_at,
                expires_at,
                revoked_at,
                last_used_at
            )
            VALUES (
                %(id)s,
                %(key_hash)s,
                %(encrypted_key_blob)s,
                %(key_prefix)s,
                %(user_id)s,
                %(status)s,
                %(created_at)s,
                %(expires_at)s,
                %(revoked_at)s,
                %(last_used_at)s
            )
            """,
            {
                "id": record.id,
                "key_hash": record.key_hash,
                "encrypted_key_blob": record.encrypted_key_blob.encode("utf-8"),
                "key_prefix": record.key_prefix,
                "user_id": record.user_id,
                "status": record.status.value,
                "created_at": record.created_at,
                "expires_at": record.expires_at,
                "revoked_at": record.revoked_at,
                "last_used_at": record.last_used_at,
            },
        )


class DynamoDbVirtualKeyCache:
    def __init__(self, table: DynamoDbTable) -> None:
        self._table = table

    def get_active_key(self, user_id: str, now: datetime) -> VirtualKeyCacheEntry | None:
        item = self._table.get_item(user_id)
        if item is None:
            return None
        ttl = int(item["ttl"])
        if ttl <= int(now.timestamp()):
            return None
        status = VirtualKeyStatus(item["status"])
        if status != VirtualKeyStatus.ACTIVE:
            return None
        return VirtualKeyCacheEntry(
            user_id=str(item["user_id"]),
            virtual_key_id=str(item["virtual_key_id"]),
            encrypted_key_ref=str(item["encrypted_key_ref"]),
            key_prefix=str(item["key_prefix"]),
            status=status,
            ttl=ttl,
        )

    def put_active_key(self, entry: VirtualKeyCacheEntry) -> None:
        payload = {
            "user_id": entry.user_id,
            "virtual_key_id": entry.virtual_key_id,
            "encrypted_key_ref": entry.encrypted_key_ref,
            "key_prefix": entry.key_prefix,
            "status": entry.status.value,
            "ttl": entry.ttl,
        }
        self._table.put_item(payload)

    def invalidate_user(self, user_id: str) -> None:
        self._table.delete_item(user_id)


class Boto3DynamoDbTable:
    def __init__(self, table: Any) -> None:
        self._table = table

    def get_item(self, user_id: str) -> Mapping[str, Any] | None:
        response = self._table.get_item(Key={"user_id": user_id})
        return response.get("Item")

    def put_item(self, item: Mapping[str, Any]) -> None:
        self._table.put_item(Item=dict(item))

    def delete_item(self, user_id: str) -> None:
        self._table.delete_item(Key={"user_id": user_id})
