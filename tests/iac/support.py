from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aws_cdk.assertions import Template

from infra.app import build_cdk_app
from infra.stack import ClaudeCodeProxyStack


def synth_stack(profile_name: str = "dev") -> ClaudeCodeProxyStack:
    _, stack = build_cdk_app(profile_name=profile_name)
    return stack


def synth_template(profile_name: str = "dev") -> Template:
    return Template.from_stack(synth_stack(profile_name=profile_name))


def resource_types(template: Template) -> list[str]:
    resources = template.to_json().get("Resources", {})
    return sorted({resource["Type"] for resource in resources.values()})


def load_snapshot(path: Path) -> Any:
    return json.loads(path.read_text())
