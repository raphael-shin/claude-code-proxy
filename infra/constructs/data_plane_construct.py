from __future__ import annotations

from constructs import Construct

from infra.config import DataPlaneConfig


class DataPlaneConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, config: DataPlaneConfig) -> None:
        super().__init__(scope, construct_id)
        self.config = config
