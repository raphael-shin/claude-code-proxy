from __future__ import annotations

from proxy.bedrock_converse.request_builder import build_converse_request
from proxy.model_resolver import ResolvedModel, ResolvedModelCapabilities


def test_request_builder_maps_minimal_anthropic_payload_to_converse() -> None:
    resolved_model = ResolvedModel(
        requested_model="claude-sonnet-4-5",
        logical_model="sonnet",
        provider="bedrock",
        bedrock_api_route="converse",
        bedrock_model_id="anthropic.claude-sonnet-4-5-v1:0",
        inference_profile_id="ip-sonnet",
        aws_region_name="us-east-1",
        capabilities=ResolvedModelCapabilities(
            supports_native_structured_output=True,
            supports_reasoning=True,
            supports_prompt_cache_ttl=True,
            supports_disable_parallel_tool_use=True,
        ),
    )

    built = build_converse_request(
        {
            "model": "claude-sonnet-4-5",
            "system": "Be concise.",
            "messages": [
                {"role": "user", "content": "Hello"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_1",
                            "name": "lookup",
                            "input": {"query": "docs"},
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_1",
                            "content": [
                                {"type": "text", "text": "done"},
                                {"type": "json", "json": {"ok": True}},
                            ],
                            "is_error": True,
                        }
                    ],
                },
            ],
            "tools": [
                {
                    "name": "lookup",
                    "description": "Lookup docs",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                }
            ],
            "tool_choice": {"type": "tool", "name": "lookup"},
            "max_tokens": 256,
            "temperature": 0.2,
            "top_p": 0.9,
            "stop_sequences": ["END"],
        },
        resolved_model=resolved_model,
    )

    assert built.operation == "converse"
    assert built.target_model_id == "anthropic.claude-sonnet-4-5-v1:0"
    assert built.inference_profile_id == "ip-sonnet"
    assert built.payload["system"] == [{"text": "Be concise."}]
    assert built.payload["messages"] == [
        {"role": "user", "content": [{"text": "Hello"}]},
        {
            "role": "assistant",
            "content": [
                {
                    "toolUse": {
                        "toolUseId": "toolu_1",
                        "name": "lookup",
                        "input": {"query": "docs"},
                    }
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": "toolu_1",
                        "status": "error",
                        "content": [
                            {"text": "done"},
                            {"json": {"ok": True}},
                        ],
                    }
                }
            ],
        },
    ]
    assert built.payload["toolConfig"]["tools"][0]["toolSpec"]["name"] == "lookup"
    assert built.payload["toolConfig"]["toolChoice"] == {"tool": {"name": "lookup"}}
    assert built.payload["inferenceConfig"] == {
        "maxTokens": 256,
        "stopSequences": ["END"],
        "temperature": 0.2,
        "topP": 0.9,
    }
    assert "invoke" not in built.operation
