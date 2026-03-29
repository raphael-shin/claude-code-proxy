from __future__ import annotations

from aws_cdk import Environment, Stack
from constructs import Construct

from infra.config import ClaudeCodeProxyStackProps
from infra.constructs import (
    AdminApiConstruct,
    DataPlaneConstruct,
    NetworkConstruct,
    ProxyRuntimeConstruct,
    TokenServiceConstruct,
)


class ClaudeCodeProxyStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        props: ClaudeCodeProxyStackProps,
    ) -> None:
        super().__init__(
            scope,
            construct_id,
            env=Environment(
                account=props.deployment_environment.account,
                region=props.deployment_environment.region,
            ),
            stack_name=props.naming.stack_name,
        )
        self.props = props
        self.network = NetworkConstruct(self, "Network", config=props.network)
        self.data_plane = DataPlaneConstruct(self, "DataPlane", config=props.data_plane)
        self.token_service = TokenServiceConstruct(self, "TokenService", config=props.token_service)
        self.admin_api = AdminApiConstruct(self, "AdminApi", config=props.admin_api)
        self.proxy_runtime = ProxyRuntimeConstruct(self, "ProxyRuntime", config=props.proxy_runtime)
