from __future__ import annotations

from aws_cdk import Duration
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

from infra.config import TokenServiceConfig
from infra.constructs.common import make_rest_api, retention_days
from infra.constructs.data_plane_construct import DataPlaneConstruct
from infra.constructs.network_construct import NetworkConstruct


class TokenServiceConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: TokenServiceConfig,
        network: NetworkConstruct | None = None,
        data_plane: DataPlaneConstruct | None = None,
    ) -> None:
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
            vpc=network.vpc if network is not None else None,
            vpc_subnets=network.private_subnet_selection if network is not None else None,
            security_groups=[network.token_service_security_group] if network is not None else None,
            environment=_lambda_environment(data_plane),
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

        self.api = make_rest_api(
            self,
            "Api",
            log_group=self.access_log_group,
            stage_name=config.stage_name,
            throttling_rate_limit=config.throttling_rate_limit,
            throttling_burst_limit=config.throttling_burst_limit,
        )
        self.token_service_resource = self.api.root.add_resource("token-service")
        self.get_or_create_key_resource = self.token_service_resource.add_resource("get-or-create-key")
        self.integration = apigateway.LambdaIntegration(self.handler)
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
        if data_plane is not None:
            data_plane.grant_access(self.handler)


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


def _lambda_environment(data_plane: DataPlaneConstruct | None) -> dict[str, str]:
    if data_plane is None:
        return {}
    return data_plane.env_vars()
