POSTGRES_SCHEMA_SQL = """
CREATE TABLE users (
    id VARCHAR(128) PRIMARY KEY,
    email VARCHAR(320) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    department VARCHAR(255),
    cost_center VARCHAR(64),
    groups TEXT[] NOT NULL DEFAULT '{}',
    proxy_access_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE identity_user_mappings (
    username VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL REFERENCES users(id),
    identity_provider VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE admin_identities (
    principal_id VARCHAR(255) PRIMARY KEY,
    role VARCHAR(32) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE virtual_keys (
    id UUID PRIMARY KEY,
    key_hash VARCHAR(64) NOT NULL UNIQUE,
    encrypted_key_blob BYTEA NOT NULL,
    key_prefix VARCHAR(16) NOT NULL,
    user_id VARCHAR(128) NOT NULL REFERENCES users(id),
    status VARCHAR(16) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ
);

CREATE TABLE teams (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    cost_center VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE team_memberships (
    id UUID PRIMARY KEY,
    team_id UUID NOT NULL REFERENCES teams(id),
    user_id VARCHAR(128) NOT NULL REFERENCES users(id),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (team_id, user_id)
);

CREATE TABLE policies (
    id UUID PRIMARY KEY,
    scope_type VARCHAR(16) NOT NULL,
    scope_id VARCHAR(128) NOT NULL,
    rule_type VARCHAR(64) NOT NULL,
    rule_value JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE budget_policies (
    id UUID PRIMARY KEY,
    scope_type VARCHAR(16) NOT NULL,
    scope_id VARCHAR(128) NOT NULL,
    period_type VARCHAR(16) NOT NULL,
    metric_type VARCHAR(16) NOT NULL,
    limit_value BIGINT NOT NULL,
    soft_limit_percent INTEGER NOT NULL,
    hard_limit_percent INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_budget_policy_thresholds CHECK (
        soft_limit_percent <= hard_limit_percent
        AND hard_limit_percent <= 100
    )
);

CREATE TABLE model_alias_rules (
    id UUID PRIMARY KEY,
    pattern VARCHAR(255) NOT NULL,
    logical_model VARCHAR(64) NOT NULL,
    priority INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE model_routes (
    id UUID PRIMARY KEY,
    logical_model VARCHAR(64) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    bedrock_api_route VARCHAR(32) NOT NULL,
    bedrock_model_id VARCHAR(255),
    inference_profile_id VARCHAR(255),
    supports_native_structured_output BOOLEAN NOT NULL DEFAULT FALSE,
    supports_reasoning BOOLEAN NOT NULL DEFAULT FALSE,
    supports_prompt_cache_ttl BOOLEAN NOT NULL DEFAULT FALSE,
    supports_disable_parallel_tool_use BOOLEAN NOT NULL DEFAULT FALSE,
    priority INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (logical_model, provider, priority)
);

CREATE TABLE model_pricing_catalog (
    id UUID PRIMARY KEY,
    provider VARCHAR(64) NOT NULL,
    model_id VARCHAR(255) NOT NULL,
    input_cost_per_million NUMERIC(18, 6) NOT NULL,
    output_cost_per_million NUMERIC(18, 6) NOT NULL,
    cache_write_input_cost_per_million NUMERIC(18, 6) NOT NULL DEFAULT 0,
    cache_read_input_cost_per_million NUMERIC(18, 6) NOT NULL DEFAULT 0,
    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
    effective_from DATE NOT NULL,
    effective_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE usage_events (
    id UUID PRIMARY KEY,
    request_id UUID NOT NULL,
    user_id VARCHAR(128) NOT NULL REFERENCES users(id),
    model VARCHAR(255) NOT NULL,
    input_tokens BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    total_tokens BIGINT NOT NULL DEFAULT 0,
    cost_usd NUMERIC(18, 6) NOT NULL DEFAULT 0,
    pricing_catalog_id UUID REFERENCES model_pricing_catalog(id),
    cache_write_input_tokens BIGINT NOT NULL DEFAULT 0,
    cache_read_input_tokens BIGINT NOT NULL DEFAULT 0,
    cache_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    estimated_cache_write_cost_usd NUMERIC(18, 6) NOT NULL DEFAULT 0,
    estimated_cache_read_cost_usd NUMERIC(18, 6) NOT NULL DEFAULT 0,
    decision VARCHAR(32) NOT NULL,
    denial_reason TEXT,
    latency_ms INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE audit_events (
    id UUID PRIMARY KEY,
    request_id UUID NOT NULL,
    actor_user_id VARCHAR(128),
    event_type VARCHAR(64) NOT NULL,
    decision VARCHAR(32) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_virtual_keys_key_hash ON virtual_keys (key_hash);
CREATE INDEX idx_virtual_keys_user_status ON virtual_keys (user_id, status);
"""
