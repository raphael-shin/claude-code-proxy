"""Create initial Claude Code Proxy schema.

Revision ID: 20260329_000001
Revises:
Create Date: 2026-03-29 02:30:00+09:00
"""

from __future__ import annotations

from alembic import op

from infra.postgres.schema import POSTGRES_SCHEMA_SQL

revision = "20260329_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    for statement in _split_sql_statements(POSTGRES_SCHEMA_SQL):
        op.execute(statement)


def downgrade() -> None:
    for table_name in [
        "audit_events",
        "usage_events",
        "model_routes",
        "model_alias_rules",
        "budget_policies",
        "policies",
        "team_memberships",
        "teams",
        "virtual_keys",
        "admin_identities",
        "identity_user_mappings",
        "users",
        "model_pricing_catalog",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")


def _split_sql_statements(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]
