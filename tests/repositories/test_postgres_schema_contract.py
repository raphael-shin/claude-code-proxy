from __future__ import annotations

from infra.postgres.schema import POSTGRES_SCHEMA_SQL


def test_schema_contract_defines_required_tables_and_constraints() -> None:
    for table_name in [
        "users",
        "identity_user_mappings",
        "admin_identities",
        "virtual_keys",
        "teams",
        "team_memberships",
        "policies",
        "budget_policies",
        "model_alias_rules",
        "model_routes",
        "usage_events",
        "audit_events",
        "model_pricing_catalog",
    ]:
        assert f"CREATE TABLE {table_name}" in POSTGRES_SCHEMA_SQL

    assert "CREATE INDEX idx_virtual_keys_key_hash ON virtual_keys (key_hash);" in POSTGRES_SCHEMA_SQL
    assert "CONSTRAINT chk_budget_policy_thresholds CHECK" in POSTGRES_SCHEMA_SQL
    assert "soft_limit_percent <= hard_limit_percent" in POSTGRES_SCHEMA_SQL
    assert "hard_limit_percent <= 100" in POSTGRES_SCHEMA_SQL
    assert "is_primary BOOLEAN NOT NULL DEFAULT FALSE" in POSTGRES_SCHEMA_SQL
    assert "bedrock_api_route VARCHAR(32) NOT NULL" in POSTGRES_SCHEMA_SQL
    assert "bedrock_model_id VARCHAR(255)" in POSTGRES_SCHEMA_SQL
    assert "inference_profile_id VARCHAR(255)" in POSTGRES_SCHEMA_SQL
    assert "supports_native_structured_output BOOLEAN NOT NULL DEFAULT FALSE" in POSTGRES_SCHEMA_SQL
    assert "supports_reasoning BOOLEAN NOT NULL DEFAULT FALSE" in POSTGRES_SCHEMA_SQL
    assert "supports_prompt_cache_ttl BOOLEAN NOT NULL DEFAULT FALSE" in POSTGRES_SCHEMA_SQL
    assert "supports_disable_parallel_tool_use BOOLEAN NOT NULL DEFAULT FALSE" in POSTGRES_SCHEMA_SQL
    assert "pricing_catalog_id UUID REFERENCES model_pricing_catalog(id)" in POSTGRES_SCHEMA_SQL
    assert "cache_write_input_tokens BIGINT NOT NULL DEFAULT 0" in POSTGRES_SCHEMA_SQL
    assert "cache_read_input_tokens BIGINT NOT NULL DEFAULT 0" in POSTGRES_SCHEMA_SQL
    assert "cache_details JSONB NOT NULL DEFAULT '{}'::jsonb" in POSTGRES_SCHEMA_SQL
    assert "estimated_cache_write_cost_usd NUMERIC(18, 6) NOT NULL DEFAULT 0" in POSTGRES_SCHEMA_SQL
    assert "estimated_cache_read_cost_usd NUMERIC(18, 6) NOT NULL DEFAULT 0" in POSTGRES_SCHEMA_SQL
    assert "cache_write_input_cost_per_million NUMERIC(18, 6) NOT NULL DEFAULT 0" in POSTGRES_SCHEMA_SQL
    assert "cache_read_input_cost_per_million NUMERIC(18, 6) NOT NULL DEFAULT 0" in POSTGRES_SCHEMA_SQL
    assert "quota_policy_id" not in POSTGRES_SCHEMA_SQL
    assert "model_policy_id" not in POSTGRES_SCHEMA_SQL
