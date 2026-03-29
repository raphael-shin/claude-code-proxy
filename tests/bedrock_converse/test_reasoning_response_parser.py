from __future__ import annotations

from proxy.bedrock_converse.response_parser import parse_converse_response


def test_response_parser_preserves_reasoning_blocks_and_raw_reasoning() -> None:
    parsed = parse_converse_response(
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "Result"},
                        {
                            "reasoningContent": {
                                "reasoningText": {"text": "step-by-step"},
                                "signature": "sig-123",
                            }
                        },
                    ],
                }
            },
            "stopReason": "guardrail_intervened",
            "usage": {
                "inputTokens": 10,
                "outputTokens": 20,
                "totalTokens": 30,
            },
        },
        model="claude-sonnet-4-5",
    )

    assert parsed["stop_reason"] == "end_turn"
    assert parsed["thinking_blocks"] == [
        {
            "type": "thinking",
            "thinking": "step-by-step",
            "signature": "sig-123",
        }
    ]
    assert parsed["provider_metadata"]["raw_stop_reason"] == "guardrail_intervened"
    assert parsed["provider_metadata"]["reasoning"] == [
        {
            "reasoningText": {"text": "step-by-step"},
            "signature": "sig-123",
        }
    ]
