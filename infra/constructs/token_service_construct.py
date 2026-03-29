from __future__ import annotations

from aws_cdk import Duration
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

from infra.config import TokenServiceConfig
from infra.constructs.common import retention_days


class TokenServiceConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, *, config: TokenServiceConfig) -> None:
        super().__init__(scope, construct_id)
        self.config = config
        self.access_log_group = logs.LogGroup(
            self,
            "AccessLogs",
            retention=retention_days(config.log_retention_days),
        )
        self.handler = lambda_.Function(
            self,
            "Handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.InlineCode(_token_service_handler_code()),
            description="token service request handler",
        )
        self.authorizer_handler: lambda_.Function | None = None
        self.authorizer: apigateway.RequestAuthorizer | None = None
        if config.authorizer.enabled:
            self.authorizer_handler = lambda_.Function(
                self,
                "RequestAuthorizerHandler",
                runtime=lambda_.Runtime.PYTHON_3_12,
                handler="index.handler",
                code=lambda_.InlineCode(_authorizer_handler_code()),
                description="token service request authorizer",
            )
            self.authorizer = apigateway.RequestAuthorizer(
                self,
                "RequestAuthorizer",
                handler=self.authorizer_handler,
                identity_sources=[
                    apigateway.IdentitySource.header(config.authorizer.identity_header)
                ],
                results_cache_ttl=Duration.seconds(config.authorizer.results_cache_ttl_seconds),
            )

        self.api = apigateway.RestApi(
            self,
            "Api",
            endpoint_types=[apigateway.EndpointType.REGIONAL],
            deploy_options=apigateway.StageOptions(
                stage_name=config.stage_name,
                throttling_rate_limit=config.throttling_rate_limit,
                throttling_burst_limit=config.throttling_burst_limit,
                access_log_destination=apigateway.LogGroupLogDestination(self.access_log_group),
                access_log_format=apigateway.AccessLogFormat.json_with_standard_fields(
                    caller=True,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True,
                ),
            ),
        )
        self.token_service_resource = self.api.root.add_resource("token-service")
        self.get_or_create_key_resource = self.token_service_resource.add_resource("get-or-create-key")
        self.integration = apigateway.LambdaIntegration(self.handler)
        self.integration_handler = self.handler
        self.post_method = self.get_or_create_key_resource.add_method(
            "POST",
            self.integration,
            authorization_type=(
                apigateway.AuthorizationType.CUSTOM
                if self.authorizer is not None
                else apigateway.AuthorizationType.IAM
            ),
            authorizer=self.authorizer,
        )
        self.web_acl_association_target_arn = self.api.deployment_stage.stage_arn


def _token_service_handler_code() -> str:
    return """
import json


def handler(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({"status": "ok", "service": "token-service"}),
    }
""".strip()


def _authorizer_handler_code() -> str:
    return """
def handler(event, context):
    return {
        "principalId": "token-service-authorizer",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": event["methodArn"],
                }
            ],
        },
    }
""".strip()
