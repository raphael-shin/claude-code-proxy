from __future__ import annotations

from typing import Any, Mapping

from proxy.bedrock_converse import SUPPORTED_STOP_REASONS


def parse_converse_response(
    response: Mapping[str, Any],
    *,
    model: str | None = None,
) -> dict[str, Any]:
    output_message = response.get("output", {}).get("message", {})
    raw_content = output_message.get("content", [])
    content_blocks: list[dict[str, Any]] = []
    thinking_blocks: list[dict[str, Any]] = []
    provider_reasoning: list[dict[str, Any]] = []

    for block in raw_content:
        if "text" in block:
            content_blocks.append({"type": "text", "text": block["text"]})
            continue
        if "toolUse" in block:
            tool_use = block["toolUse"]
            content_blocks.append(
                {
                    "type": "tool_use",
                    "id": tool_use["toolUseId"],
                    "name": tool_use["name"],
                    "input": tool_use.get("input", {}),
                }
            )
            continue
        if "reasoningContent" in block:
            reasoning = block["reasoningContent"]
            provider_reasoning.append(reasoning)
            reasoning_text = reasoning.get("reasoningText", {}).get("text", "")
            thinking_block = {
                "type": "thinking",
                "thinking": reasoning_text,
            }
            if reasoning.get("signature") is not None:
                thinking_block["signature"] = reasoning["signature"]
            thinking_blocks.append(thinking_block)

    stop_reason, provider_metadata = _map_stop_reason(response.get("stopReason"))
    if provider_reasoning:
        provider_metadata["reasoning"] = provider_reasoning

    parsed = {
        "id": response.get("requestMetadata", {}).get("requestId", "msg_bedrock"),
        "type": "message",
        "role": output_message.get("role", "assistant"),
        "model": model,
        "content": content_blocks,
        "stop_reason": stop_reason,
        "stop_sequence": response.get("stopSequence"),
        "usage": _normalize_usage(response.get("usage")),
    }
    if thinking_blocks:
        parsed["thinking_blocks"] = thinking_blocks
    if provider_metadata:
        parsed["provider_metadata"] = provider_metadata
    return parsed


def _map_stop_reason(raw_stop_reason: str | None) -> tuple[str | None, dict[str, Any]]:
    if raw_stop_reason is None:
        return None, {}
    if raw_stop_reason in SUPPORTED_STOP_REASONS:
        return raw_stop_reason, {}
    return "end_turn", {"raw_stop_reason": raw_stop_reason}


def _normalize_usage(usage: Mapping[str, Any] | None) -> dict[str, Any]:
    usage = usage or {}
    return {
        "input_tokens": int(usage.get("inputTokens", 0) or 0),
        "output_tokens": int(usage.get("outputTokens", 0) or 0),
        "total_tokens": int(usage.get("totalTokens", 0) or 0),
        "cache_write_input_tokens": int(usage.get("cacheWriteInputTokens", 0) or 0),
        "cache_read_input_tokens": int(usage.get("cacheReadInputTokens", 0) or 0),
        "cache_details": usage.get("cacheDetails"),
    }
