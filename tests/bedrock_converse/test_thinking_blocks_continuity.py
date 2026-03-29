from __future__ import annotations

from proxy.bedrock_converse.request_builder import build_converse_request
from proxy.model_resolver import ResolvedModel, ResolvedModelCapabilities


def test_request_builder_replays_thinking_blocks_for_follow_up_turns() -> None:
    built = build_converse_request(
        {
            "messages": [
                {
                    "role": "assistant",
                    "thinking_blocks": [
                        {
                            "type": "thinking",
                            "thinking": "previous chain of thought",
                            "signature": "sig-1",
                        }
                    ],
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_1",
                            "name": "lookup",
                            "input": {"query": "history"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_1",
                            "content": "done",
                        }
                    ],
                },
            ],
            "reasoning_effort": "medium",
        },
        resolved_model=_resolved_model(),
    )

    assert built.reasoning_enabled is True
    assert built.payload["messages"][0]["content"][0] == {
        "reasoningContent": {
            "reasoningText": {"text": "previous chain of thought"},
            "signature": "sig-1",
        }
    }


def test_request_builder_disables_reasoning_when_thinking_blocks_are_missing() -> None:
    built = build_converse_request(
        {
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_1",
                            "name": "lookup",
                            "input": {"query": "history"},
                        }
                    ],
                }
            ],
            "reasoning_effort": "high",
        },
        resolved_model=_resolved_model(),
    )

    assert built.reasoning_enabled is False
    assert "additionalModelRequestFields" not in built.payload


def _resolved_model() -> ResolvedModel:
    return ResolvedModel(
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
    )
