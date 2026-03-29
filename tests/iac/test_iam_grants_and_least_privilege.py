from __future__ import annotations

from aws_cdk.assertions import Template

from infra.app import build_cdk_app


def test_runtime_and_token_service_roles_use_scoped_grants_without_admin_policies() -> None:
    _, stack = build_cdk_app("dev")
    template = Template.from_stack(stack)

    role_resources = template.find_resources("AWS::IAM::Role")
    for role in role_resources.values():
        managed_policies = role["Properties"].get("ManagedPolicyArns", [])
        rendered = [str(policy) for policy in managed_policies]
        assert not any("AdministratorAccess" in policy for policy in rendered)

    statements = list(_policy_statements(template))
    actions = [_as_list(statement["Action"]) for statement in statements]
    bedrock_statements = [
        statement
        for statement in statements
        if any(
            action in {"bedrock:Converse", "bedrock:ConverseStream"}
            for action in _as_list(statement["Action"])
        )
    ]

    assert any("dynamodb:GetItem" in action_list for action_list in actions)
    assert any("secretsmanager:GetSecretValue" in action_list for action_list in actions)
    assert any("bedrock:Converse" in action_list for action_list in actions)
    assert any("bedrock:ConverseStream" in action_list for action_list in actions)
    assert all("*" not in action_list for action_list in actions)
    assert all("bedrock:*" not in action_list for action_list in actions)
    assert bedrock_statements
    for statement in bedrock_statements:
        resources = _as_list(statement["Resource"])
        assert "*" not in resources
        rendered_resources = [str(resource) for resource in resources]
        assert any("foundation-model/anthropic." in resource for resource in rendered_resources)
        assert any("inference-profile/" in resource and "anthropic." in resource for resource in rendered_resources)


def _policy_statements(template: Template) -> list[dict]:
    policies = template.find_resources("AWS::IAM::Policy")
    statements: list[dict] = []
    for policy in policies.values():
        policy_document = policy["Properties"]["PolicyDocument"]
        statements.extend(policy_document["Statement"])
    return statements


def _as_list(value):
    if isinstance(value, list):
        return value
    return [value]
