from __future__ import annotations

import pytest
from aws_cdk import App

from infra.app import build_cdk_app
from infra.config import ClaudeCodeProxyStackProps, default_environment_name, load_profile


def test_load_profile_returns_typed_stack_props() -> None:
    props = load_profile("staging")

    assert isinstance(props, ClaudeCodeProxyStackProps)
    assert props.naming.environment == "staging"
    assert props.token_service.stage_name == "staging"
    assert props.admin_api.stage_name == "admin-staging"
    assert props.network.vpc_cidr == "10.52.0.0/16"
    assert props.proxy_runtime.idle_timeout_seconds == 300


def test_app_builds_stack_from_typed_profile_props() -> None:
    _, stack = build_cdk_app("prod")

    assert stack.props.naming.stack_name == "ClaudeCodeProxy-prod"
    assert stack.region == "ap-northeast-2"
    assert stack.props.deployment_environment.account == "333333333333"
    assert stack.props.proxy_runtime.domain_name == "proxy.example.com"


def test_unknown_profile_uses_default_template(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CDK_DEFAULT_ACCOUNT", "444444444444")
    monkeypatch.setenv("CDK_DEFAULT_REGION", "us-west-2")

    props = load_profile("my-team")

    assert props.naming.environment == "my-team"
    assert props.naming.stack_name == "ClaudeCodeProxy-my-team"
    assert props.deployment_environment.account == "444444444444"
    assert props.deployment_environment.region == "us-west-2"
    assert props.token_service.stage_name == "my-team"
    assert props.admin_api.stage_name == "admin-my-team"
    assert props.proxy_runtime.domain_name == "proxy.my-team.example.internal"


def test_default_environment_name_prefers_aws_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_CODE_PROXY_ENV", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "personal_sandbox")

    assert default_environment_name() == "personal-sandbox"


def test_explicit_environment_overrides_aws_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_PROXY_ENV", "manual-env")
    monkeypatch.setenv("AWS_PROFILE", "personal_sandbox")

    assert default_environment_name() == "manual-env"


def test_cdk_context_environment_name_is_supported() -> None:
    app = App(context={"envName": "context-env"})

    _, stack = build_cdk_app(app=app)

    assert stack.props.naming.environment == "context-env"
    assert stack.props.naming.stack_name == "ClaudeCodeProxy-context-env"
