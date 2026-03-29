from __future__ import annotations

import pytest
from aws_cdk import App

from infra.app import build_cdk_app
from infra.config import ClaudeCodeProxyStackProps, build_stack_props, default_environment_name


def test_build_stack_props_returns_typed_props(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CDK_DEFAULT_ACCOUNT", "111111111111")
    monkeypatch.setenv("CDK_DEFAULT_REGION", "ap-northeast-2")

    props = build_stack_props("my-team")

    assert isinstance(props, ClaudeCodeProxyStackProps)
    assert props.naming.environment == "my-team"
    assert props.token_service.stage_name == "my-team"
    assert props.admin_api.stage_name == "admin-my-team"
    assert props.deployment_environment.account == "111111111111"
    assert props.deployment_environment.region == "ap-northeast-2"
    assert props.proxy_runtime.image_repository_name == "claude-code-proxy/runtime"
    assert props.proxy_runtime.image_tag == "latest"
    assert props.proxy_runtime.idle_timeout_seconds == 300


def test_build_stack_props_reads_account_and_region_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CDK_DEFAULT_ACCOUNT", "444444444444")
    monkeypatch.setenv("CDK_DEFAULT_REGION", "us-west-2")

    props = build_stack_props("sandbox")

    assert props.naming.stack_name == "ClaudeCodeProxy-sandbox"
    assert props.deployment_environment.account == "444444444444"
    assert props.deployment_environment.region == "us-west-2"
    assert props.proxy_runtime.domain_name == "proxy.sandbox.example.internal"


def test_build_stack_props_reads_runtime_image_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_PROXY_RUNTIME_IMAGE_REPOSITORY_NAME", "team/proxy-runtime")
    monkeypatch.setenv("CLAUDE_CODE_PROXY_RUNTIME_IMAGE_TAG", "2026-03-29")

    props = build_stack_props("sandbox")

    assert props.proxy_runtime.image_repository_name == "team/proxy-runtime"
    assert props.proxy_runtime.image_tag == "2026-03-29"


def test_build_stack_props_normalizes_environment_name() -> None:
    props = build_stack_props("My_Sandbox")

    assert props.naming.environment == "my-sandbox"
    assert props.token_service.stage_name == "my-sandbox"


def test_default_environment_name_prefers_claude_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_PROXY_ENV", "manual-env")
    monkeypatch.setenv("AWS_PROFILE", "personal_sandbox")

    assert default_environment_name() == "manual-env"


def test_default_environment_name_falls_back_to_aws_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_CODE_PROXY_ENV", raising=False)
    monkeypatch.setenv("AWS_PROFILE", "personal_sandbox")

    assert default_environment_name() == "personal-sandbox"


def test_cdk_context_environment_name_is_supported() -> None:
    app = App(context={"envName": "context-env"})

    _, stack = build_cdk_app(app=app)

    assert stack.props.naming.environment == "context-env"
    assert stack.props.naming.stack_name == "ClaudeCodeProxy-context-env"
