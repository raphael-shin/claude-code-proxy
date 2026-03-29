from __future__ import annotations

from aws_cdk.assertions import Match, Template

from infra.app import build_cdk_app


def test_stack_declares_minimal_ops_defaults_without_tracing_or_otel_overlays() -> None:
    _, stack = build_cdk_app("dev")
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::ElasticLoadBalancingV2::TargetGroup",
        Match.object_like({"HealthCheckPath": "/health"}),
    )
    template.resource_count_is("AWS::XRay::Group", 0)
    template.resource_count_is("AWS::XRay::SamplingRule", 0)

    log_groups = template.find_resources("AWS::Logs::LogGroup")
    assert log_groups
    assert all(
        resource["Properties"].get("RetentionInDays") is not None
        for resource in log_groups.values()
    )

    lambda_functions = template.find_resources("AWS::Lambda::Function")
    assert lambda_functions
    for function in lambda_functions.values():
        tracing = function["Properties"].get("TracingConfig", {})
        assert tracing.get("Mode") != "Active"

    task_definitions = template.find_resources("AWS::ECS::TaskDefinition")
    assert task_definitions
    for task_definition in task_definitions.values():
        for container in task_definition["Properties"]["ContainerDefinitions"]:
            environment_names = {
                entry["Name"] for entry in container.get("Environment", [])
            }
            assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in environment_names
            assert "AWS_XRAY_DAEMON_ADDRESS" not in environment_names
