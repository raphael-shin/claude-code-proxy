from __future__ import annotations

from typing import Any

import jsii
from aws_cdk import Annotations, IAspect
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from constructs import IConstruct


@jsii.implements(IAspect)
class SecurityGuardsAspect:
    def visit(self, node: IConstruct) -> None:
        if isinstance(node, logs.CfnLogGroup):
            self._guard_log_group_retention(node)
            return
        if isinstance(node, dynamodb.CfnTable):
            self._guard_table_encryption(node)
            return
        if isinstance(node, ecs.CfnService):
            self._guard_service_networking(node)
            return
        if isinstance(node, rds.CfnDBCluster):
            self._guard_cluster_encryption(node)
            return
        if isinstance(node, rds.CfnDBInstance):
            self._guard_instance_networking(node)

    @staticmethod
    def _guard_log_group_retention(node: logs.CfnLogGroup) -> None:
        if node.retention_in_days is not None:
            return
        Annotations.of(node).add_error(
            "Security guard: CloudWatch log groups must set retention_in_days."
        )

    @staticmethod
    def _guard_table_encryption(node: dynamodb.CfnTable) -> None:
        sse = node.sse_specification
        if isinstance(sse, dict):
            enabled = sse.get("sseEnabled")
        else:
            enabled = getattr(sse, "sse_enabled", None)
        if enabled is True:
            return
        Annotations.of(node).add_error(
            "Security guard: DynamoDB tables must enable server-side encryption."
        )

    @staticmethod
    def _guard_service_networking(node: ecs.CfnService) -> None:
        assign_public_ip = _service_assign_public_ip(node.network_configuration)
        if assign_public_ip == "ENABLED":
            Annotations.of(node).add_error(
                "Security guard: ECS services must not assign public IP addresses."
            )

    @staticmethod
    def _guard_cluster_encryption(node: rds.CfnDBCluster) -> None:
        if node.storage_encrypted is False or node.storage_encrypted is None:
            Annotations.of(node).add_error(
                "Security guard: RDS clusters must enable storage encryption."
            )

    @staticmethod
    def _guard_instance_networking(node: rds.CfnDBInstance) -> None:
        if node.publicly_accessible is True:
            Annotations.of(node).add_error(
                "Security guard: RDS instances must not be publicly accessible."
            )


def _service_assign_public_ip(network_configuration: Any) -> str | None:
    if network_configuration is None:
        return None
    if isinstance(network_configuration, dict):
        awsvpc = network_configuration.get("awsvpcConfiguration") or network_configuration.get(
            "AwsvpcConfiguration"
        )
    else:
        awsvpc = getattr(network_configuration, "awsvpc_configuration", None)
    if awsvpc is None:
        return None
    if isinstance(awsvpc, dict):
        return awsvpc.get("assignPublicIp") or awsvpc.get("AssignPublicIp")
    return getattr(awsvpc, "assign_public_ip", None)
