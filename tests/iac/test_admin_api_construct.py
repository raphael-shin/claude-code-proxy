from __future__ import annotations

from aws_cdk import App, Stack
from aws_cdk.assertions import Match, Template

from infra.config import AdminApiConfig
from infra.constructs.admin_api_construct import AdminApiConstruct


def test_admin_api_construct_declares_dedicated_admin_gateway_with_iam_and_logs() -> None:
    app = App()
    stack = Stack(app, "AdminApiHarness")
    construct = AdminApiConstruct(
        stack,
        "AdminApi",
        config=AdminApiConfig(
            stage_name="admin-dev",
            throttling_rate_limit=10,
            throttling_burst_limit=20,
            log_retention_days=30,
        ),
    )
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::ApiGateway::RestApi",
        {"EndpointConfiguration": {"Types": ["REGIONAL"]}},
    )
    template.has_resource_properties(
        "AWS::ApiGateway::Stage",
        Match.object_like(
            {
                "StageName": "admin-dev",
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
                                "ThrottlingBurstLimit": 20,
                                "ThrottlingRateLimit": 10,
                            }
                        )
                    ]
                ),
            }
        ),
    )
    template.has_resource_properties("AWS::ApiGateway::Resource", {"PathPart": "admin"})
    template.has_resource_properties("AWS::ApiGateway::Resource", {"PathPart": "users"})
    template.has_resource_properties(
        "AWS::ApiGateway::Method",
        Match.object_like(
            {
                "HttpMethod": "GET",
                "AuthorizationType": "AWS_IAM",
                "Integration": Match.object_like({"Type": "AWS_PROXY"}),
            }
        ),
    )
    assert construct.users_resource.path == "/admin/users"
    assert construct.config.stage_name == "admin-dev"
    assert "/stages/" in construct.web_acl_association_target_arn
