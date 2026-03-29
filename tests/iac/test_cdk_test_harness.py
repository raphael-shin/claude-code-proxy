from __future__ import annotations

import json

from aws_cdk import App, Duration, Stack, aws_sqs as sqs
from aws_cdk.assertions import Template

from tests.iac.support import load_snapshot, resource_types


def test_cdk_test_harness_prefers_template_assertions_and_snapshot_fixture(iac_snapshot_dir) -> None:
    app = App()
    stack = Stack(app, "HarnessStack")
    sqs.Queue(stack, "Queue", visibility_timeout=Duration.seconds(30))

    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "VisibilityTimeout": 30,
        },
    )

    snapshot = load_snapshot(iac_snapshot_dir / "harness_resource_types.json")
    assert resource_types(template) == snapshot
