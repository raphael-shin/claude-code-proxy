from __future__ import annotations

import argparse

from aws_cdk import App

from infra.config import ClaudeCodeProxyStackProps, default_environment_name, load_profile
from infra.stack import ClaudeCodeProxyStack

ENV_NAME_CONTEXT_KEY = "envName"


def build_cdk_app(
    environment_name: str | None = None,
    *,
    app: App | None = None,
) -> tuple[App, ClaudeCodeProxyStack]:
    resolved_app = app or App()
    props = load_profile(
        _resolve_environment_name(
            resolved_app,
            explicit_name=environment_name,
        )
    )
    stack = create_stack(resolved_app, props=props)
    return resolved_app, stack


def create_stack(app: App, *, props: ClaudeCodeProxyStackProps) -> ClaudeCodeProxyStack:
    return ClaudeCodeProxyStack(
        app,
        "ClaudeCodeProxyStack",
        props=props,
    )


def main(argv: list[str] | None = None) -> App:
    parser = argparse.ArgumentParser(description="Claude Code Proxy CDK app")
    parser.add_argument(
        "--env-name",
        "--profile",
        dest="environment_name",
        default=None,
        help=(
            "logical deployment environment name; defaults to CDK context "
            f"'{ENV_NAME_CONTEXT_KEY}', then CLAUDE_CODE_PROXY_ENV, then "
            "AWS_PROFILE, then dev"
        ),
    )
    args = parser.parse_args(argv)

    app, _ = build_cdk_app(environment_name=args.environment_name)
    app.synth()
    return app


def _resolve_environment_name(app: App, *, explicit_name: str | None) -> str:
    if explicit_name is not None and explicit_name.strip():
        return explicit_name

    context_name = app.node.try_get_context(ENV_NAME_CONTEXT_KEY)
    if isinstance(context_name, str) and context_name.strip():
        return context_name

    return default_environment_name()


if __name__ == "__main__":
    main()
