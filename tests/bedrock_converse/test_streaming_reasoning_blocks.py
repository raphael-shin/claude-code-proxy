from __future__ import annotations

import json

from proxy.bedrock_converse.stream_decoder import ConverseStreamDecoder


def test_stream_decoder_preserves_reasoning_blocks_and_raw_reasoning() -> None:
    decoder = ConverseStreamDecoder(model="claude-sonnet-4-5")

    frames = list(
        decoder.iter_sse_events(
            [
                {"messageStart": {"role": "assistant"}},
                {
                    "contentBlockStart": {
                        "contentBlockIndex": 0,
                        "start": {"reasoningContent": {}},
                    }
                },
                {
                    "contentBlockDelta": {
                        "contentBlockIndex": 0,
                        "delta": {"reasoningContent": {"text": "step"}},
                    }
                },
                {"contentBlockStop": {"contentBlockIndex": 0}},
                {"messageStop": {"stopReason": "end_turn"}},
                {"metadata": {"usage": {"inputTokens": 1, "outputTokens": 2, "totalTokens": 3}}},
            ]
        )
    )

    thinking_delta_payload = json.loads(frames[2].split("data: ", 1)[1])
    assert thinking_delta_payload["delta"] == {
        "type": "thinking_delta",
        "thinking": "step",
    }
    assert decoder.thinking_blocks == [{"type": "thinking", "thinking": "step"}]
    assert decoder.provider_reasoning == [{"reasoningText": {"text": "step"}}]
