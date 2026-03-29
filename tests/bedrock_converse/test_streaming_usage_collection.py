from __future__ import annotations

from proxy.bedrock_converse.stream_decoder import StreamingUsageCollector


def test_streaming_usage_collector_preserves_provider_usage_fields() -> None:
    collector = StreamingUsageCollector()

    collector.update_from_metadata(
        {
            "metadata": {
                "usage": {
                    "inputTokens": 10,
                    "outputTokens": 20,
                    "totalTokens": 30,
                    "cacheWriteInputTokens": None,
                    "cacheReadInputTokens": None,
                    "cacheDetails": {"ttl": "5m"},
                }
            }
        }
    )

    assert collector.usage == {
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
        "cache_write_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_details": {"ttl": "5m"},
    }
