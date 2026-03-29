from __future__ import annotations

from typing import Any


class FakeBedrockClient:
    def __init__(self) -> None:
        self.converse_calls: list[Any] = []
        self.converse_stream_calls: list[Any] = []
        self.count_tokens_calls: list[Any] = []

    def converse(self, converse_request: Any) -> dict[str, Any]:
        self.converse_calls.append(converse_request)
        return {}

    def converse_stream(self, converse_request: Any) -> list[dict[str, Any]]:
        self.converse_stream_calls.append(converse_request)
        return []

    def count_tokens(self, converse_request: Any) -> dict[str, Any]:
        self.count_tokens_calls.append(converse_request)
        return {}
