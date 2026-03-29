from __future__ import annotations

from aws_cdk import App, Stack
from aws_cdk.assertions import Match, Template

from tests.iac.support import make_network_and_data_plane


def test_network_and_data_plane_constructs_stay_in_one_stack_with_proxy_first_db_access() -> None:
    app = App()
    stack = Stack(app, "DataPlaneHarness")
    _, data_plane = make_network_and_data_plane(stack)
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
    assert data_plane.database_endpoint == data_plane.database_proxy.endpoint
