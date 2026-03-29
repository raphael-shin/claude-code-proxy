from __future__ import annotations

from aws_cdk import App, Stack
from aws_cdk.assertions import Match, Template

from infra.config import DataPlaneConfig, NetworkConfig
from infra.constructs.data_plane_construct import DataPlaneConstruct
from infra.constructs.network_construct import NetworkConstruct


def test_network_and_data_plane_constructs_stay_in_one_stack_with_proxy_first_db_access() -> None:
    app = App()
    stack = Stack(app, "DataPlaneHarness")
    network = NetworkConstruct(
        stack,
        "Network",
        config=NetworkConfig(
            vpc_cidr="10.42.0.0/16",
            max_azs=2,
            nat_gateways=1,
        ),
    )
    construct = DataPlaneConstruct(
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
    template = Template.from_stack(stack)

    template.has_resource_properties("AWS::EC2::VPC", {"CidrBlock": "10.42.0.0/16"})
    template.has_resource_properties(
        "AWS::RDS::DBCluster",
        Match.object_like(
            {
                "Engine": "aurora-postgresql",
                "DatabaseName": "claude_code_proxy",
                "ServerlessV2ScalingConfiguration": {
                    "MinCapacity": 0.5,
                    "MaxCapacity": 2,
                },
            }
        ),
    )
    template.has_resource_properties(
        "AWS::RDS::DBProxy",
        Match.object_like(
            {
                "EngineFamily": "POSTGRESQL",
                "RequireTLS": True,
            }
        ),
    )
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        Match.object_like(
            {
                "BillingMode": "PAY_PER_REQUEST",
                "TimeToLiveSpecification": {
                    "AttributeName": "ttl",
                    "Enabled": True,
                },
            }
        ),
    )
    assert construct.database_endpoint == construct.database_proxy.endpoint
