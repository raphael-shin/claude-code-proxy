from __future__ import annotations

from aws_cdk import App, Stack
from aws_cdk.assertions import Match, Template

from infra.config import TokenServiceConfig
from infra.constructs.token_service_construct import TokenServiceConstruct


def test_token_service_construct_declares_regional_iam_api_with_logs_and_throttling() -> None:
    template, construct = _token_service_template(
        TokenServiceConfig(
            stage_name="dev",
            throttling_rate_limit=25,
            throttling_burst_limit=50,
            log_retention_days=14,
        )
    )

    template.has_resource_properties(
        "AWS::ApiGateway::RestApi",
        {"EndpointConfiguration": {"Types": ["REGIONAL"]}},
    )
    template.has_resource_properties(
        "AWS::ApiGateway::Stage",
        Match.object_like(
            {
                "StageName": "dev",
                "AccessLogSetting": Match.object_like(
                    {
                        "DestinationArn": Match.any_value(),
                        "Format": Match.any_value(),
                    }
                ),
                "MethodSettings": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "HttpMethod": "*",
                                "ResourcePath": "/*",
                                "ThrottlingBurstLimit": 50,
                                "ThrottlingRateLimit": 25,
                            }
                        )
                    ]
                ),
            }
        ),
    )
    template.has_resource_properties(
        "AWS::ApiGateway::Method",
        Match.object_like(
            {
                "HttpMethod": "POST",
                "AuthorizationType": "AWS_IAM",
                "Integration": Match.object_like({"Type": "AWS_PROXY"}),
            }
        ),
    )
    template.has_resource_properties(
        "AWS::Lambda::Permission",
        Match.object_like(
            {
                "Action": "lambda:InvokeFunction",
                "Principal": "apigateway.amazonaws.com",
            }
        ),
    )
    assert construct.config.stage_name == "dev"
    assert "/stages/" in construct.web_acl_association_target_arn


def _token_service_template(
    config: TokenServiceConfig,
) -> tuple[Template, TokenServiceConstruct]:
    app = App()
    stack = Stack(app, "TokenServiceHarness")
    construct = TokenServiceConstruct(stack, "TokenService", config=config)
    return Template.from_stack(stack), construct
