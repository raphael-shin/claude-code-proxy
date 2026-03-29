from __future__ import annotations

from constructs import Construct

from infra.config import ProxyRuntimeConfig


class ProxyRuntimeConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, config: ProxyRuntimeConfig) -> None:
        super().__init__(scope, construct_id)
        self.config = config
