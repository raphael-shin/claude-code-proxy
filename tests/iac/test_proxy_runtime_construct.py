from __future__ import annotations

from aws_cdk import App, Stack
from aws_cdk.assertions import Match, Template

from infra.config import ProxyRuntimeConfig
from infra.constructs.proxy_runtime_construct import ProxyRuntimeConstruct
from tests.iac.support import make_network_and_data_plane


def test_proxy_runtime_construct_declares_cluster_service_alb_and_health_checks() -> None:
    app = App()
    stack = Stack(app, "ProxyRuntimeHarness")
    network, data_plane = make_network_and_data_plane(stack)
    ProxyRuntimeConstruct(
        stack,
        "ProxyRuntime",
        config=_runtime_config(),
        network=network,
        data_plane=data_plane,
    )
    template = Template.from_stack(stack)

    template.resource_count_is("AWS::ECS::Cluster", 1)
    template.resource_count_is("AWS::ECS::TaskDefinition", 1)
    template.has_resource_properties(
        "AWS::ECS::Service",
        Match.object_like(
            {
                "DesiredCount": 2,
                "LaunchType": "FARGATE",
                "NetworkConfiguration": Match.object_like(
                    {
                        "AwsvpcConfiguration": Match.object_like(
                            {
                                "AssignPublicIp": "DISABLED",
                                "Subnets": Match.any_value(),
                            }
                        )
                    }
                ),
            }
        ),
    )
    template.has_resource_properties(
        "AWS::ElasticLoadBalancingV2::LoadBalancer",
        Match.object_like(
            {
                "Scheme": "internet-facing",
                "LoadBalancerAttributes": Match.array_with(
                    [
                        Match.object_like(
                            {
                                "Key": "idle_timeout.timeout_seconds",
                                "Value": "300",
                            }
                        )
                    ]
                ),
            }
        ),
    )
    template.has_resource_properties(
        "AWS::ElasticLoadBalancingV2::TargetGroup",
        Match.object_like(
            {
                "HealthCheckPath": "/health",
                "Port": 8000,
                "Protocol": "HTTP",
                "TargetType": "ip",
            }
        ),
    )


def _runtime_config() -> ProxyRuntimeConfig:
    return ProxyRuntimeConfig(
        container_port=8000,
        desired_count=2,
        min_capacity=2,
        max_capacity=4,
        cpu=512,
        memory_mib=1024,
        health_check_path="/health",
        idle_timeout_seconds=300,
        log_retention_days=30,
        domain_name="proxy.dev.example.internal",
        hosted_zone_name="dev.example.internal",
        certificate_arn="arn:aws:acm:ap-northeast-2:111111111111:certificate/dev-placeholder",
        waf_arn="arn:aws:wafv2:ap-northeast-2:111111111111:regional/webacl/dev-placeholder/00000000-0000-0000-0000-000000000000",
    )
