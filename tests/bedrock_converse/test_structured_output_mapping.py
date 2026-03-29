from __future__ import annotations

import pytest

from proxy.bedrock_converse.request_builder import BedrockRequestBuildError, build_converse_request
from proxy.model_resolver import ResolvedModel, ResolvedModelCapabilities


def test_request_builder_creates_native_output_config_with_strict_schema() -> None:
    resolved_model = _resolved_model(native_structured_output=True)

    built = build_converse_request(
        {
            "messages": [{"role": "user", "content": "Return JSON"}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "ticket",
                    "description": "Structured ticket payload",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "ticket": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                },
                            }
                        },
                    },
                },
            },
        },
        resolved_model=resolved_model,
    )

    schema = built.payload["outputConfig"]["textFormat"]["structure"]["jsonSchema"]["schema"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["ticket"]["additionalProperties"] is False
    assert built.payload["outputConfig"]["textFormat"]["structure"]["jsonSchema"]["name"] == "ticket"
    assert built.payload["outputConfig"]["textFormat"]["structure"]["jsonSchema"]["description"] == "Structured ticket payload"


@pytest.mark.parametrize(
    ("native_structured_output", "response_format"),
    [
        (
            False,
            {
                "type": "json_schema",
                "json_schema": {
                    "schema": {
                        "type": "object",
                        "properties": {"answer": {"type": "string"}},
                    }
                },
            },
        ),
        (True, {"type": "json_object"}),
    ],
)
def test_request_builder_rejects_unsupported_structured_output(
    native_structured_output: bool,
    response_format: dict[str, object],
) -> None:
    with pytest.raises(BedrockRequestBuildError) as error_info:
        build_converse_request(
            {
                "messages": [{"role": "user", "content": "Return JSON"}],
                "response_format": response_format,
            },
            resolved_model=_resolved_model(native_structured_output=native_structured_output),
        )

    assert error_info.value.reason == "structured_output_not_supported"


def _resolved_model(*, native_structured_output: bool) -> ResolvedModel:
    return ResolvedModel(
        requested_model="claude-sonnet-4-5",
        logical_model="sonnet",
        provider="bedrock",
        bedrock_api_route="converse",
        bedrock_model_id="anthropic.claude-sonnet-4-5-v1:0",
        inference_profile_id=None,
        aws_region_name="us-east-1",
        capabilities=ResolvedModelCapabilities(
            supports_native_structured_output=native_structured_output,
            supports_reasoning=True,
            supports_prompt_cache_ttl=True,
            supports_disable_parallel_tool_use=True,
        ),
    )
