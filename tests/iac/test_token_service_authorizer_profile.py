from __future__ import annotations

from aws_cdk.assertions import Match

from infra.config import OptionalAuthorizerConfig, TokenServiceConfig

from tests.iac.support import token_service_template


def test_token_service_profile_can_attach_request_authorizer_without_moving_handler_logic() -> None:
    template, construct = token_service_template(
        TokenServiceConfig(
            stage_name="dev",
            throttling_rate_limit=25,
            throttling_burst_limit=50,
            log_retention_days=14,
            authorizer=OptionalAuthorizerConfig(
                enabled=True,
                identity_header="X-Proxy-Auth",
                results_cache_ttl_seconds=300,
            ),
        )
    )

    template.resource_count_is("AWS::Lambda::Function", 2)
    template.has_resource_properties(
        "AWS::ApiGateway::Authorizer",
        Match.object_like(
            {
                "Type": "REQUEST",
                "AuthorizerResultTtlInSeconds": 300,
                "IdentitySource": "method.request.header.X-Proxy-Auth",
            }
        ),
    )
    template.has_resource_properties(
        "AWS::ApiGateway::Method",
        Match.object_like(
            {
                "HttpMethod": "POST",
                "AuthorizationType": "CUSTOM",
                "AuthorizerId": Match.any_value(),
            }
        ),
    )
    assert construct.authorizer_handler is not None
    assert construct.authorizer_handler is not construct.handler
