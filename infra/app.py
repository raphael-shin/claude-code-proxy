from __future__ import annotations

import argparse

from aws_cdk import App

from infra.config import ClaudeCodeProxyStackProps, load_profile
from infra.stack import ClaudeCodeProxyStack


def build_cdk_app(profile_name: str = "dev") -> tuple[App, ClaudeCodeProxyStack]:
    app = App()
    props = load_profile(profile_name)
    stack = create_stack(app, props=props)
    return app, stack


def create_stack(app: App, *, props: ClaudeCodeProxyStackProps) -> ClaudeCodeProxyStack:
    return ClaudeCodeProxyStack(
        app,
        "ClaudeCodeProxyStack",
        props=props,
    )


def main(argv: list[str] | None = None) -> App:
    parser = argparse.ArgumentParser(description="Claude Code Proxy CDK app")
    parser.add_argument("--profile", default="dev", help="deployment profile name")
    args = parser.parse_args(argv)

    app, _ = build_cdk_app(profile_name=args.profile)
    app.synth()
    return app


if __name__ == "__main__":
    main()
