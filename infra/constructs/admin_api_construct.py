from __future__ import annotations

from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

from infra.config import AdminApiConfig
from infra.constructs.common import (
    lambda_observability_defaults,
    make_lambda_log_group,
    make_rest_api,
    retention_days,
)


class AdminApiConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, config: AdminApiConfig) -> None:
        super().__init__(scope, construct_id)
        self.config = config
        self.access_log_group = logs.LogGroup(
            self,
            "AccessLogs",
            retention=retention_days(config.log_retention_days),
        )
        self.handler_log_group = make_lambda_log_group(
            self,
            "HandlerLogGroup",
            log_retention_days=config.log_retention_days,
        )
        self.handler = lambda_.Function(
            self,
            "Handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.InlineCode(_admin_handler_code()),
            description="admin api request handler",
            **lambda_observability_defaults(log_group=self.handler_log_group),
        )
        self.api = make_rest_api(
            self,
            "Api",
            log_group=self.access_log_group,
            stage_name=config.stage_name,
            throttling_rate_limit=config.throttling_rate_limit,
            throttling_burst_limit=config.throttling_burst_limit,
        )
        self.admin_resource = self.api.root.add_resource("admin")
        self.users_resource = self.admin_resource.add_resource("users")
        self.integration = apigateway.LambdaIntegration(self.handler)
        self.get_users_method = self.users_resource.add_method(
            "GET",
            self.integration,
            authorization_type=apigateway.AuthorizationType.IAM,
        )
        self.web_acl_association_target_arn = self.api.deployment_stage.stage_arn


def _admin_handler_code() -> str:
    return """
import json


def handler(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({"status": "ok", "service": "admin-api"}),
    }
""".strip()
