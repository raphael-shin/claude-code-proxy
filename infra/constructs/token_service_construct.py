from __future__ import annotations

from constructs import Construct

from infra.config import TokenServiceConfig


class TokenServiceConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, config: TokenServiceConfig) -> None:
        super().__init__(scope, construct_id)
        self.config = config
