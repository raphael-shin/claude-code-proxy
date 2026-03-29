from __future__ import annotations

import pytest

from infra.app import build_cdk_app
from infra.config import ClaudeCodeProxyStackProps, load_profile


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


def test_unknown_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown profile"):
        load_profile("qa")
