from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from testcontainers.postgres import PostgresContainer

from infra.postgres.schema import POSTGRES_SCHEMA_SQL
from models.domain import UserRecord, VirtualKeyRecord, VirtualKeyStatus
from repositories.admin_identity_repository import PostgresAdminIdentityRepository, PsycopgAdminIdentityStore
from repositories.user_repository import PostgresUserRepository, PsycopgUserStore
from repositories.virtual_key_repository import PostgresVirtualKeyRepository, PsycopgVirtualKeyStore


def _split_sql_statements(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


@pytest.fixture()
def postgres_connection():
    with PostgresContainer("postgres:16-alpine") as postgres:
        connection = psycopg.connect(
            host=postgres.get_container_host_ip(),
            port=postgres.get_exposed_port(5432),
            dbname=postgres.dbname,
            user=postgres.username,
            password=postgres.password,
            autocommit=True,
            row_factory=dict_row,
        )
        for statement in _split_sql_statements(POSTGRES_SCHEMA_SQL):
            connection.execute(statement)
        yield connection
        connection.close()


def test_postgres_repositories_support_mapping_admin_lookup_and_virtual_key_persistence(postgres_connection) -> None:
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    postgres_connection.execute(
        """
        INSERT INTO users (
            id, email, display_name, department, cost_center, groups,
            proxy_access_enabled, is_active, created_at, updated_at
        )
        VALUES (
            %(id)s, %(email)s, %(display_name)s, %(department)s, %(cost_center)s, %(groups)s,
            %(proxy_access_enabled)s, %(is_active)s, %(created_at)s, %(updated_at)s
        )
        """,
        {
            "id": "user-1",
            "email": "dev@example.com",
            "display_name": "Dev One",
            "department": "platform",
            "cost_center": "cc-1",
            "groups": ["eng", "platform"],
            "proxy_access_enabled": True,
            "is_active": True,
            "created_at": created_at,
            "updated_at": created_at,
        },
    )
    postgres_connection.execute(
        """
        INSERT INTO identity_user_mappings (username, user_id, identity_provider, created_at)
        VALUES (%(username)s, %(user_id)s, %(identity_provider)s, %(created_at)s)
        """,
        {
            "username": "alice",
            "user_id": "user-1",
            "identity_provider": "identity-center",
            "created_at": created_at,
        },
    )
    postgres_connection.execute(
        """
        INSERT INTO admin_identities (principal_id, role, is_active, created_at, updated_at)
        VALUES (%(principal_id)s, %(role)s, %(is_active)s, %(created_at)s, %(updated_at)s)
        """,
        {
            "principal_id": "admin:alice",
            "role": "auditor",
            "is_active": True,
            "created_at": created_at,
            "updated_at": created_at,
        },
    )
    postgres_connection.execute(
        """
        INSERT INTO virtual_keys (
            id, key_hash, encrypted_key_blob, key_prefix, user_id, status, created_at
        )
        VALUES (
            %(id)s, %(key_hash)s, %(encrypted_key_blob)s, %(key_prefix)s, %(user_id)s, %(status)s, %(created_at)s
        )
        """,
        {
            "id": str(uuid4()),
            "key_hash": "hash-existing",
            "encrypted_key_blob": b"enc::vk_existing",
            "key_prefix": "vk_existing",
            "user_id": "user-1",
            "status": "active",
            "created_at": created_at,
        },
    )

    user_repository = PostgresUserRepository(PsycopgUserStore(postgres_connection))
    admin_repository = PostgresAdminIdentityRepository(PsycopgAdminIdentityStore(postgres_connection))
    virtual_key_repository = PostgresVirtualKeyRepository(PsycopgVirtualKeyStore(postgres_connection))

    assert user_repository.get_user_id_for_username("alice") == "user-1"
    assert user_repository.get_user("user-1") == UserRecord(
        id="user-1",
        email="dev@example.com",
        display_name="Dev One",
        department="platform",
        cost_center="cc-1",
        groups=("eng", "platform"),
        proxy_access_enabled=True,
        is_active=True,
        created_at=created_at,
        updated_at=created_at,
    )
    assert admin_repository.get_admin_role("admin:alice") == "auditor"

    reused_key = virtual_key_repository.get_active_key_for_user("user-1")
    assert reused_key is not None
    assert reused_key.encrypted_key_blob == "enc::vk_existing"
    assert reused_key.status == VirtualKeyStatus.ACTIVE

    new_record = VirtualKeyRecord(
        id=str(uuid4()),
        user_id="user-1",
        key_hash="hash-new",
        encrypted_key_blob="enc::vk_new",
        key_prefix="vk_new",
        status=VirtualKeyStatus.ACTIVE,
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    virtual_key_repository.save_key(new_record)

    latest_key = virtual_key_repository.get_active_key_for_user("user-1")
    assert latest_key == new_record
