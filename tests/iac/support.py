from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aws_cdk import App, Stack
from aws_cdk.assertions import Template

from infra.app import build_cdk_app
from infra.config import DataPlaneConfig, NetworkConfig, TokenServiceConfig
from infra.constructs.data_plane_construct import DataPlaneConstruct
from infra.constructs.network_construct import NetworkConstruct
from infra.constructs.token_service_construct import TokenServiceConstruct
from infra.stack import ClaudeCodeProxyStack


def synth_stack(environment_name: str = "dev") -> ClaudeCodeProxyStack:
    _, stack = build_cdk_app(environment_name)
    return stack


def synth_template(environment_name: str = "dev") -> Template:
    return Template.from_stack(synth_stack(environment_name=environment_name))


def resource_types(template: Template) -> list[str]:
    resources = template.to_json().get("Resources", {})
    return sorted({resource["Type"] for resource in resources.values()})


def load_snapshot(path: Path) -> Any:
    return json.loads(path.read_text())


def make_network_config() -> NetworkConfig:
    return NetworkConfig(
        vpc_cidr="10.42.0.0/16",
        max_azs=2,
    )


def make_data_plane_config() -> DataPlaneConfig:
    return DataPlaneConfig(
        database_name="claude_code_proxy",
        min_acu=0.5,
        max_acu=2.0,
        cache_ttl_minutes=15,
    )


def make_network_and_data_plane(
    stack: Stack,
) -> tuple[NetworkConstruct, DataPlaneConstruct]:
    network = NetworkConstruct(stack, "Network", config=make_network_config())
    data_plane = DataPlaneConstruct(
        stack, "DataPlane", config=make_data_plane_config(), network=network
    )
    return network, data_plane


def token_service_template(
    config: TokenServiceConfig,
) -> tuple[Template, TokenServiceConstruct]:
    app = App()
    stack = Stack(app, "TokenServiceHarness")
    construct = TokenServiceConstruct(stack, "TokenService", config=config)
    return Template.from_stack(stack), construct
