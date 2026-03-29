DEFAULT_MESSAGE_ID = "msg_bedrock"
DEFAULT_STREAM_MESSAGE_ID = "msg_bedrock_stream"

SUPPORTED_STOP_REASONS = {
    "end_turn",
    "max_tokens",
    "stop_sequence",
    "tool_use",
}

from proxy.bedrock_converse.request_builder import BedrockRequestBuildError, ConverseRequest, build_converse_request
from proxy.bedrock_converse.response_parser import normalize_usage, parse_converse_response
from proxy.bedrock_converse.stream_decoder import ConverseStreamDecoder, StreamingUsageCollector

__all__ = [
    "BedrockRequestBuildError",
    "ConverseRequest",
    "ConverseStreamDecoder",
    "SUPPORTED_STOP_REASONS",
    "StreamingUsageCollector",
    "build_converse_request",
    "normalize_usage",
    "parse_converse_response",
]
