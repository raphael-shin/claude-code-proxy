from __future__ import annotations

from aws_cdk import App, Aspects, Stack
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk.assertions import Annotations, Match

from infra.aspects import SecurityGuardsAspect
from infra.app import build_cdk_app


def test_security_guards_accept_stack_defaults() -> None:
    _, stack = build_cdk_app("dev")

    annotations = Annotations.from_stack(stack)

    assert not annotations.find_error("*", Match.string_like_regexp("Security guard:.*"))


def test_security_guards_flag_public_tasks_and_unencrypted_tables() -> None:
    app = App()
    stack = Stack(app, "SecurityResourceHarness")
    Aspects.of(stack).add(SecurityGuardsAspect())
    logs.CfnLogGroup(stack, "MissingRetentionLogGroup")
    dynamodb.CfnTable(
        stack,
        "UnencryptedTable",
        attribute_definitions=[
            dynamodb.CfnTable.AttributeDefinitionProperty(
                attribute_name="id",
                attribute_type="S",
            )
        ],
        key_schema=[
            dynamodb.CfnTable.KeySchemaProperty(
                attribute_name="id",
                key_type="HASH",
            )
        ],
        billing_mode="PAY_PER_REQUEST",
    )
    ecs.CfnService(
        stack,
        "PublicService",
        cluster="cluster-arn",
        desired_count=1,
        launch_type="FARGATE",
        task_definition="task-definition-arn",
        network_configuration={
            "awsvpcConfiguration": {
                "subnets": ["subnet-123"],
                "securityGroups": ["sg-123"],
                "assignPublicIp": "ENABLED",
            }
        },
    )
    rds.CfnDBInstance(
        stack,
        "PublicDatabase",
        allocated_storage="20",
        db_instance_class="db.t3.micro",
        engine="postgres",
        master_username="proxyapp",
        master_user_password="password123!",
        publicly_accessible=True,
    )

    annotations = Annotations.from_stack(stack)

    annotations.has_error(
        "*",
        Match.string_like_regexp("Security guard: CloudWatch log groups must set retention_in_days.*"),
    )
    annotations.has_error(
        "*",
        Match.string_like_regexp("Security guard: DynamoDB tables must enable server-side encryption.*"),
    )
    annotations.has_error(
        "*",
        Match.string_like_regexp("Security guard: ECS services must not assign public IP addresses.*"),
    )
    annotations.has_error(
        "*",
        Match.string_like_regexp("Security guard: RDS instances must not be publicly accessible.*"),
    )
