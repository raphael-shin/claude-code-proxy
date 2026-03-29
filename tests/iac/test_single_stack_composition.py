from __future__ import annotations

from aws_cdk import NestedStack, Stack

from infra.app import build_cdk_app
from infra.stack import ClaudeCodeProxyStack


def test_cdk_app_uses_single_claude_code_proxy_stack() -> None:
    app, stack = build_cdk_app("dev")

    stacks = [child for child in app.node.children if isinstance(child, Stack)]

    assert len(stacks) == 1
    assert stacks[0] is stack
    assert isinstance(stack, ClaudeCodeProxyStack)
    assert stack.stack_name == "ClaudeCodeProxy-dev"
    assert stack.node.try_find_child("Network") is stack.network
    assert stack.node.try_find_child("DataPlane") is stack.data_plane
    assert stack.node.try_find_child("TokenService") is stack.token_service
    assert stack.node.try_find_child("AdminApi") is stack.admin_api
    assert stack.node.try_find_child("ProxyRuntime") is stack.proxy_runtime


def test_stack_does_not_introduce_nested_stacks() -> None:
    _, stack = build_cdk_app("dev")

    nested = [child for child in stack.node.find_all() if isinstance(child, NestedStack)]

    assert nested == []
