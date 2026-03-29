from __future__ import annotations

from proxy.bedrock_converse.request_builder import build_converse_request
from proxy.model_resolver import ResolvedModel, ResolvedModelCapabilities


def test_request_builder_normalizes_reasoning_and_relaxes_forced_tool_choice() -> None:
    built = build_converse_request(
        {
            "messages": [{"role": "user", "content": "Think carefully"}],
            "tools": [
                {
                    "name": "lookup",
                    "input_schema": {"type": "object"},
                }
            ],
            "tool_choice": {"type": "tool", "name": "lookup"},
            "reasoning_effort": "low",
            "parallel_tool_calls": False,
        },
        resolved_model=ResolvedModel(
            requested_model="claude-sonnet-4-5",
            logical_model="sonnet",
            provider="bedrock",
            bedrock_api_route="converse",
            bedrock_model_id="anthropic.claude-sonnet-4-5-v1:0",
            inference_profile_id=None,
            aws_region_name="us-east-1",
            capabilities=ResolvedModelCapabilities(
                supports_native_structured_output=True,
                supports_reasoning=True,
                supports_prompt_cache_ttl=True,
                supports_disable_parallel_tool_use=True,
            ),
        ),
    )

    assert built.reasoning_enabled is True
    assert built.payload["additionalModelRequestFields"]["thinking"] == {
        "type": "enabled",
        "budget_tokens": 1024,
    }
    assert built.payload["additionalModelRequestFields"]["disable_parallel_tool_use"] is True
    assert built.payload["toolConfig"]["toolChoice"] == {"auto": {}}
