from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from proxy.model_resolver import ResolvedModel

REASON_INVALID_ROLE = "invalid_role"
REASON_INVALID_CONTENT = "invalid_content"
REASON_STRUCTURED_OUTPUT_NOT_SUPPORTED = "structured_output_not_supported"

SUPPORTED_MESSAGE_ROLES = {"user", "assistant"}
REASONING_BUDGETS = {
    "low": 1024,
    "medium": 4096,
    "high": 8192,
}
MIN_REASONING_BUDGET_TOKENS = 1024


class BedrockRequestBuildError(ValueError):
    def __init__(self, *, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True, slots=True)
class ConverseRequest:
    operation: str
    target_model_id: str
    inference_profile_id: str | None
    payload: dict[str, Any]
    reasoning_enabled: bool = False


def build_converse_request(
    request: Mapping[str, Any],
    *,
    resolved_model: ResolvedModel,
) -> ConverseRequest:
    requested_reasoning = _normalize_reasoning_request(
        request=request,
        resolved_model=resolved_model,
    )
    reasoning_enabled = requested_reasoning is not None and _has_reasoning_continuity(request.get("messages", []))

    payload: dict[str, Any] = {
        "messages": _normalize_messages(
            request.get("messages", []),
            include_thinking_blocks=reasoning_enabled,
        ),
    }

    system_blocks = _normalize_system_blocks(request.get("system"))
    if system_blocks:
        payload["system"] = system_blocks

    inference_config = _build_inference_config(request)
    if inference_config:
        payload["inferenceConfig"] = inference_config

    tool_config = _build_tool_config(
        request=request,
        resolved_model=resolved_model,
        reasoning_enabled=reasoning_enabled,
    )
    if tool_config:
        payload["toolConfig"] = tool_config

    additional_fields = _build_additional_model_request_fields(
        request=request,
        resolved_model=resolved_model,
        requested_reasoning=requested_reasoning if reasoning_enabled else None,
    )
    if additional_fields:
        payload["additionalModelRequestFields"] = additional_fields

    output_config = _build_output_config(request=request, resolved_model=resolved_model)
    if output_config:
        payload["outputConfig"] = output_config

    operation = "converse_stream" if bool(request.get("stream")) else "converse"
    target_model_id = resolved_model.bedrock_model_id or resolved_model.inference_profile_id or ""
    return ConverseRequest(
        operation=operation,
        target_model_id=target_model_id,
        inference_profile_id=resolved_model.inference_profile_id,
        payload=payload,
        reasoning_enabled=reasoning_enabled,
    )


def _normalize_system_blocks(system: Any) -> list[dict[str, Any]]:
    if system is None:
        return []
    if isinstance(system, str):
        return [{"text": system}]
    if isinstance(system, Sequence) and not isinstance(system, (str, bytes, bytearray)):
        blocks: list[dict[str, Any]] = []
        for block in system:
            if isinstance(block, str):
                blocks.append({"text": block})
                continue
            if isinstance(block, Mapping) and block.get("type") == "text":
                blocks.append({"text": str(block.get("text", ""))})
                continue
            if isinstance(block, Mapping):
                blocks.append(dict(block))
                continue
            raise BedrockRequestBuildError(
                reason=REASON_INVALID_CONTENT,
                message="Unsupported system block.",
            )
        return blocks
    raise BedrockRequestBuildError(
        reason=REASON_INVALID_CONTENT,
        message="Unsupported system prompt format.",
    )


def _normalize_messages(
    messages: Any,
    *,
    include_thinking_blocks: bool,
) -> list[dict[str, Any]]:
    normalized_messages: list[dict[str, Any]] = []
    for raw_message in messages:
        if not isinstance(raw_message, Mapping):
            raise BedrockRequestBuildError(
                reason=REASON_INVALID_CONTENT,
                message="Each message must be an object.",
            )
        role = str(raw_message.get("role", ""))
        if role not in SUPPORTED_MESSAGE_ROLES:
            raise BedrockRequestBuildError(
                reason=REASON_INVALID_ROLE,
                message=f"Unsupported message role '{role}'.",
            )
        normalized_content = _normalize_content_blocks(
            raw_message.get("content"),
            role=role,
            thinking_blocks=raw_message.get("thinking_blocks") if include_thinking_blocks else None,
        )
        normalized_messages.append({"role": role, "content": normalized_content})
    return normalized_messages


def _normalize_content_blocks(
    content: Any,
    *,
    role: str,
    thinking_blocks: Any,
) -> list[dict[str, Any]]:
    blocks = _coerce_blocks(content)
    normalized: list[dict[str, Any]] = []
    if role == "assistant" and thinking_blocks:
        normalized.extend(_normalize_thinking_blocks(thinking_blocks))
    for block in blocks:
        if isinstance(block, str):
            normalized.append({"text": block})
            continue
        if not isinstance(block, Mapping):
            raise BedrockRequestBuildError(
                reason=REASON_INVALID_CONTENT,
                message="Unsupported content block.",
            )
        block_type = block.get("type")
        if block_type == "text":
            normalized.append({"text": str(block.get("text", ""))})
            continue
        if block_type == "tool_use" and role == "assistant":
            normalized.append(
                {
                    "toolUse": {
                        "toolUseId": str(block.get("id", "")),
                        "name": str(block.get("name", "")),
                        "input": block.get("input", {}),
                    }
                }
            )
            continue
        if block_type == "tool_result" and role == "user":
            normalized.append(
                {
                    "toolResult": {
                        "toolUseId": str(block.get("tool_use_id", "")),
                        "status": "error" if bool(block.get("is_error")) else "success",
                        "content": _normalize_tool_result_content(block.get("content")),
                    }
                }
            )
            continue
        if block_type in {"image", "document"}:
            passthrough = dict(block)
            passthrough.pop("type", None)
            normalized.append({block_type: passthrough})
            continue
        raise BedrockRequestBuildError(
            reason=REASON_INVALID_CONTENT,
            message=f"Unsupported content block type '{block_type}'.",
        )
    return normalized


def _coerce_blocks(content: Any) -> list[Any]:
    if content is None:
        return []
    if isinstance(content, str):
        return [content]
    if isinstance(content, Sequence) and not isinstance(content, (str, bytes, bytearray)):
        return list(content)
    raise BedrockRequestBuildError(
        reason=REASON_INVALID_CONTENT,
        message="Message content must be a string or list of blocks.",
    )


def _normalize_tool_result_content(content: Any) -> list[dict[str, Any]]:
    if content is None:
        return []
    if isinstance(content, str):
        return [{"text": content}]

    normalized: list[dict[str, Any]] = []
    for block in _coerce_blocks(content):
        if isinstance(block, str):
            normalized.append({"text": block})
            continue
        if not isinstance(block, Mapping):
            raise BedrockRequestBuildError(
                reason=REASON_INVALID_CONTENT,
                message="Unsupported tool result content block.",
            )
        block_type = block.get("type")
        if block_type == "text":
            normalized.append({"text": str(block.get("text", ""))})
            continue
        if block_type == "json":
            normalized.append({"json": block.get("json", {})})
            continue
        raise BedrockRequestBuildError(
            reason=REASON_INVALID_CONTENT,
            message=f"Unsupported tool result block type '{block_type}'.",
        )
    return normalized


def _normalize_thinking_blocks(thinking_blocks: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for block in _coerce_blocks(thinking_blocks):
        if not isinstance(block, Mapping):
            raise BedrockRequestBuildError(
                reason=REASON_INVALID_CONTENT,
                message="Unsupported thinking block.",
            )
        if block.get("type") != "thinking":
            continue
        reasoning_text = str(block.get("thinking", ""))
        raw_reasoning = {"reasoningText": {"text": reasoning_text}}
        if block.get("signature"):
            raw_reasoning["signature"] = block["signature"]
        normalized.append({"reasoningContent": raw_reasoning})
    return normalized


def _build_inference_config(request: Mapping[str, Any]) -> dict[str, Any]:
    inference_config: dict[str, Any] = {}
    if request.get("max_tokens") is not None:
        inference_config["maxTokens"] = request["max_tokens"]
    if request.get("stop_sequences") is not None:
        inference_config["stopSequences"] = list(request["stop_sequences"])
    if request.get("temperature") is not None:
        inference_config["temperature"] = request["temperature"]
    if request.get("top_p") is not None:
        inference_config["topP"] = request["top_p"]
    return inference_config


def _build_tool_config(
    *,
    request: Mapping[str, Any],
    resolved_model: ResolvedModel,
    reasoning_enabled: bool,
) -> dict[str, Any] | None:
    tools = request.get("tools") or []
    tool_choice = request.get("tool_choice")
    if not tools and tool_choice is None:
        return None

    tool_config: dict[str, Any] = {}
    if tools:
        tool_config["tools"] = [
            {
                "toolSpec": {
                    "name": str(tool.get("name", "")),
                    "description": tool.get("description"),
                    "inputSchema": {
                        "json": _normalize_schema(tool.get("input_schema", {"type": "object"}))
                    },
                }
            }
            for tool in tools
        ]
    mapped_tool_choice = _map_tool_choice(
        tool_choice=tool_choice,
        supports_disable_parallel_tool_use=resolved_model.capabilities.supports_disable_parallel_tool_use,
        reasoning_enabled=reasoning_enabled,
    )
    if mapped_tool_choice is not None:
        tool_config["toolChoice"] = mapped_tool_choice
    return tool_config


def _map_tool_choice(
    *,
    tool_choice: Any,
    supports_disable_parallel_tool_use: bool,
    reasoning_enabled: bool,
) -> dict[str, Any] | None:
    del supports_disable_parallel_tool_use
    if tool_choice is None:
        return None
    if reasoning_enabled:
        return {"auto": {}}
    if not isinstance(tool_choice, Mapping):
        return {"auto": {}}
    choice_type = tool_choice.get("type")
    if choice_type == "tool":
        return {"tool": {"name": str(tool_choice.get("name", ""))}}
    if choice_type == "any":
        return {"any": {}}
    return {"auto": {}}


def _build_additional_model_request_fields(
    *,
    request: Mapping[str, Any],
    resolved_model: ResolvedModel,
    requested_reasoning: dict[str, Any] | None,
) -> dict[str, Any] | None:
    additional_fields: dict[str, Any] = {}
    if (
        request.get("parallel_tool_calls") is False
        and resolved_model.capabilities.supports_disable_parallel_tool_use
    ):
        additional_fields["disable_parallel_tool_use"] = True
    if requested_reasoning is not None:
        additional_fields["thinking"] = requested_reasoning
    return additional_fields or None


def _normalize_reasoning_request(
    *,
    request: Mapping[str, Any],
    resolved_model: ResolvedModel,
) -> dict[str, Any] | None:
    if not resolved_model.capabilities.supports_reasoning:
        return None
    thinking = request.get("thinking")
    reasoning_effort = request.get("reasoning_effort")
    if thinking is None and reasoning_effort is None:
        return None
    budget_tokens = MIN_REASONING_BUDGET_TOKENS
    if isinstance(thinking, Mapping) and thinking.get("budget_tokens") is not None:
        budget_tokens = max(int(thinking["budget_tokens"]), MIN_REASONING_BUDGET_TOKENS)
    elif isinstance(reasoning_effort, str):
        budget_tokens = REASONING_BUDGETS.get(reasoning_effort, REASONING_BUDGETS["medium"])
    return {
        "type": "enabled",
        "budget_tokens": budget_tokens,
    }


def _build_output_config(
    *,
    request: Mapping[str, Any],
    resolved_model: ResolvedModel,
) -> dict[str, Any] | None:
    response_format = request.get("response_format")
    if response_format is None:
        return None
    if not isinstance(response_format, Mapping):
        raise BedrockRequestBuildError(
            reason=REASON_STRUCTURED_OUTPUT_NOT_SUPPORTED,
            message="Unsupported structured output configuration.",
        )

    if response_format.get("type") == "json_object":
        raise BedrockRequestBuildError(
            reason=REASON_STRUCTURED_OUTPUT_NOT_SUPPORTED,
            message="Schema-less structured output is not supported.",
        )

    json_schema = response_format.get("json_schema")
    schema = None
    if isinstance(json_schema, Mapping):
        schema = json_schema.get("schema")
    if not resolved_model.capabilities.supports_native_structured_output or not isinstance(schema, Mapping):
        raise BedrockRequestBuildError(
            reason=REASON_STRUCTURED_OUTPUT_NOT_SUPPORTED,
            message="Native structured output is not supported for this model.",
        )

    normalized_schema = _normalize_schema(schema)
    schema_payload: dict[str, Any] = {
        "schema": normalized_schema,
    }
    if json_schema.get("name") is not None:
        schema_payload["name"] = json_schema["name"]
    if json_schema.get("description") is not None:
        schema_payload["description"] = json_schema["description"]
    return {
        "textFormat": {
            "type": "json_schema",
            "structure": {
                "jsonSchema": schema_payload,
            },
        }
    }


def _normalize_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(dict(schema))
    _inject_additional_properties_false(normalized)
    return normalized


def _inject_additional_properties_false(node: Any) -> None:
    if isinstance(node, list):
        for item in node:
            _inject_additional_properties_false(item)
        return
    if not isinstance(node, dict):
        return
    if node.get("type") == "object":
        node.setdefault("additionalProperties", False)
    for key in ("properties", "$defs", "definitions"):
        value = node.get(key)
        if isinstance(value, dict):
            for nested in value.values():
                _inject_additional_properties_false(nested)
    for key in ("items", "anyOf", "allOf", "oneOf"):
        _inject_additional_properties_false(node.get(key))


def _has_reasoning_continuity(messages: Any) -> bool:
    for raw_message in messages or []:
        if not isinstance(raw_message, Mapping) or raw_message.get("role") != "assistant":
            continue
        content = raw_message.get("content")
        blocks = _coerce_blocks(content)
        has_tool_use = any(
            isinstance(block, Mapping) and block.get("type") == "tool_use"
            for block in blocks
        )
        if has_tool_use and not raw_message.get("thinking_blocks"):
            return False
    return True
