from __future__ import annotations

from aws_cdk import App, Stack
from aws_cdk.assertions import Match, Template

from infra.config import DataPlaneConfig, NetworkConfig, ProxyRuntimeConfig
from infra.constructs.data_plane_construct import DataPlaneConstruct
from infra.constructs.network_construct import NetworkConstruct
from infra.constructs.proxy_runtime_construct import ProxyRuntimeConstruct


def test_proxy_runtime_construct_declares_cluster_service_alb_and_health_checks() -> None:
    app = App()
    stack = Stack(app, "ProxyRuntimeHarness")
    network = NetworkConstruct(
        stack,
        "Network",
        config=NetworkConfig(
            vpc_cidr="10.42.0.0/16",
            max_azs=2,
            nat_gateways=1,
        ),
    )
    data_plane = DataPlaneConstruct(
        stack,
        "DataPlane",
        config=DataPlaneConfig(
            database_name="claude_code_proxy",
            min_acu=0.5,
            max_acu=2.0,
            cache_ttl_minutes=15,
        ),
        network=network,
    )
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
