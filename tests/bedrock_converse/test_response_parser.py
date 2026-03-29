from __future__ import annotations

from proxy.bedrock_converse.response_parser import parse_converse_response


def test_response_parser_maps_minimal_bedrock_payload() -> None:
    parsed = parse_converse_response(
        {
            "requestMetadata": {"requestId": "msg-123"},
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "Hello from Bedrock"},
                        {
                            "toolUse": {
                                "toolUseId": "toolu_1",
                                "name": "lookup",
                                "input": {"query": "docs"},
                            }
                        },
                    ],
                }
            },
            "stopReason": "tool_use",
            "usage": {
                "inputTokens": 11,
                "outputTokens": 22,
                "totalTokens": 33,
                "cacheWriteInputTokens": 4,
                "cacheReadInputTokens": 5,
                "cacheDetails": {"ttl": "5m"},
            },
        },
        model="claude-sonnet-4-5",
    )

    assert parsed["id"] == "msg-123"
    assert parsed["type"] == "message"
    assert parsed["role"] == "assistant"
    assert parsed["model"] == "claude-sonnet-4-5"
    assert parsed["content"] == [
        {"type": "text", "text": "Hello from Bedrock"},
        {
            "type": "tool_use",
            "id": "toolu_1",
            "name": "lookup",
            "input": {"query": "docs"},
        },
    ]
    assert parsed["stop_reason"] == "tool_use"
    assert parsed["usage"] == {
        "input_tokens": 11,
        "output_tokens": 22,
        "total_tokens": 33,
        "cache_write_input_tokens": 4,
        "cache_read_input_tokens": 5,
        "cache_details": {"ttl": "5m"},
    }
