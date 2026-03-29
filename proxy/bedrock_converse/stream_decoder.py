from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

SUPPORTED_STOP_REASONS = {
    "end_turn",
    "max_tokens",
    "stop_sequence",
    "tool_use",
}


@dataclass(slots=True)
class StreamingUsageCollector:
    _usage: dict[str, Any] = field(
        default_factory=lambda: {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cache_write_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_details": None,
        }
    )

    def update_from_metadata(self, metadata_event: dict[str, Any]) -> None:
        metadata = metadata_event.get("metadata", metadata_event)
        usage = metadata.get("usage", {})
        self._usage = {
            "input_tokens": int(usage.get("inputTokens", 0) or 0),
            "output_tokens": int(usage.get("outputTokens", 0) or 0),
            "total_tokens": int(usage.get("totalTokens", 0) or 0),
            "cache_write_input_tokens": int(usage.get("cacheWriteInputTokens", 0) or 0),
            "cache_read_input_tokens": int(usage.get("cacheReadInputTokens", 0) or 0),
            "cache_details": usage.get("cacheDetails"),
        }

    @property
    def usage(self) -> dict[str, Any]:
        return dict(self._usage)


@dataclass(slots=True)
class ConverseStreamDecoder:
    model: str | None = None
    message_id: str = "msg_bedrock_stream"
    usage_collector: StreamingUsageCollector = field(default_factory=StreamingUsageCollector)
    thinking_blocks: list[dict[str, Any]] = field(default_factory=list)
    provider_reasoning: list[dict[str, Any]] = field(default_factory=list)
    _block_types: dict[int, str] = field(default_factory=dict)
    _thinking_block_positions: dict[int, int] = field(default_factory=dict)
    _pending_stop_reason: str | None = None

    def iter_sse_events(self, events: Iterable[dict[str, Any]]) -> Iterator[str]:
        for event in events:
            if "messageStart" in event:
                yield _sse_frame(
                    "message_start",
                    {
                        "type": "message_start",
                        "message": {
                            "id": self.message_id,
                            "type": "message",
                            "role": event["messageStart"].get("role", "assistant"),
                            "model": self.model,
                            "content": [],
                        },
                    },
                )
                continue

            if "contentBlockStart" in event:
                block_start = event["contentBlockStart"]
                block_index = int(block_start["contentBlockIndex"])
                content_block = self._normalize_content_block_start(
                    block_index,
                    block_start.get("start", {}),
                )
                yield _sse_frame(
                    "content_block_start",
                    {
                        "type": "content_block_start",
                        "index": block_index,
                        "content_block": content_block,
                    },
                )
                continue

            if "contentBlockDelta" in event:
                block_delta = event["contentBlockDelta"]
                block_index = int(block_delta["contentBlockIndex"])
                delta_payload = self._normalize_content_block_delta(
                    block_index,
                    block_delta.get("delta", {}),
                )
                yield _sse_frame(
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": block_index,
                        "delta": delta_payload,
                    },
                )
                continue

            if "contentBlockStop" in event:
                yield _sse_frame(
                    "content_block_stop",
                    {
                        "type": "content_block_stop",
                        "index": int(event["contentBlockStop"]["contentBlockIndex"]),
                    },
                )
                continue

            if "messageStop" in event:
                self._pending_stop_reason = event["messageStop"].get("stopReason")
                continue

            if "metadata" in event:
                self.usage_collector.update_from_metadata(event)
                yield from self._flush_pending_stop()
                continue

            if "exception" in event:
                yield _sse_frame(
                    "error",
                    {
                        "type": "error",
                        "error": {
                            "type": "api_error",
                            "message": str(event["exception"]),
                        },
                    },
                )
                return

        yield from self._flush_pending_stop()

    @property
    def final_usage(self) -> dict[str, Any]:
        return self.usage_collector.usage

    def _normalize_content_block_start(
        self,
        block_index: int,
        start: dict[str, Any],
    ) -> dict[str, Any]:
        if "text" in start:
            self._block_types[block_index] = "text"
            return {"type": "text", "text": ""}
        if "toolUse" in start:
            self._block_types[block_index] = "tool_use"
            tool_use = start["toolUse"]
            return {
                "type": "tool_use",
                "id": tool_use.get("toolUseId"),
                "name": tool_use.get("name"),
                "input": {},
            }
        if "reasoningContent" in start:
            self._block_types[block_index] = "thinking"
            self._thinking_block_positions[block_index] = len(self.thinking_blocks)
            self.thinking_blocks.append({"type": "thinking", "thinking": ""})
            self.provider_reasoning.append({"reasoningText": {"text": ""}})
            return {"type": "thinking", "thinking": ""}
        self._block_types[block_index] = "text"
        return {"type": "text", "text": ""}

    def _normalize_content_block_delta(
        self,
        block_index: int,
        delta: dict[str, Any],
    ) -> dict[str, Any]:
        if "text" in delta:
            return {"type": "text_delta", "text": delta["text"]}
        if "toolUse" in delta:
            return {
                "type": "input_json_delta",
                "partial_json": delta["toolUse"].get("input", ""),
            }
        if "reasoningContent" in delta:
            reasoning_text = delta["reasoningContent"].get("text", "")
            block_position = self._thinking_block_positions[block_index]
            self.thinking_blocks[block_position]["thinking"] += reasoning_text
            self.provider_reasoning[block_position]["reasoningText"]["text"] += reasoning_text
            return {"type": "thinking_delta", "thinking": reasoning_text}
        return {"type": "text_delta", "text": ""}

    def _flush_pending_stop(self) -> Iterator[str]:
        if self._pending_stop_reason is None:
            return
        stop_reason = (
            self._pending_stop_reason
            if self._pending_stop_reason in SUPPORTED_STOP_REASONS
            else "end_turn"
        )
        yield _sse_frame(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {
                    "stop_reason": stop_reason,
                    "stop_sequence": None,
                },
                "usage": self.final_usage,
            },
        )
        yield _sse_frame("message_stop", {"type": "message_stop"})
        self._pending_stop_reason = None


def _sse_frame(event_name: str, payload: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"
