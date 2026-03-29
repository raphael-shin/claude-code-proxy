from __future__ import annotations

from aws_cdk import App, Stack
from aws_cdk.assertions import Match, Template

from infra.constructs.proxy_runtime_construct import ProxyRuntimeConstruct
from tests.iac.support import make_network_and_data_plane
from tests.iac.test_proxy_runtime_construct import _runtime_config


def test_proxy_runtime_construct_adds_https_waf_deployment_controls_and_outputs() -> None:
    app = App()
    stack = Stack(app, "ProxyRuntimeEdgeHarness")
    network, data_plane = make_network_and_data_plane(stack)
    ProxyRuntimeConstruct(
        stack,
        "ProxyRuntime",
        config=_runtime_config(),
        network=network,
        data_plane=data_plane,
    )
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::ElasticLoadBalancingV2::Listener",
        Match.object_like(
            {
                "Port": 443,
                "Protocol": "HTTPS",
                "Certificates": Match.any_value(),
            }
        ),
    )
    template.resource_count_is("AWS::WAFv2::WebACLAssociation", 1)
    template.has_resource_properties(
        "AWS::ECS::Service",
        Match.object_like(
            {
                "DeploymentConfiguration": Match.object_like(
                    {
                        "DeploymentCircuitBreaker": {
                            "Enable": True,
                            "Rollback": True,
                        }
                    }
                )
            }
        ),
    )
    template.resource_count_is("AWS::ApplicationAutoScaling::ScalableTarget", 1)
    template.resource_count_is("AWS::ApplicationAutoScaling::ScalingPolicy", 1)
    template.has_resource_properties(
        "AWS::Logs::LogGroup",
        Match.object_like({"RetentionInDays": 30}),
    )
    template.has_output("RuntimeEndpointUrl", Match.any_value())
    template.has_output("RuntimeAlbDnsName", Match.any_value())
    template.has_output("RuntimeHttpsListenerArn", Match.any_value())
