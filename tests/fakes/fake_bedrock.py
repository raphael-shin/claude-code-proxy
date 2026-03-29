from __future__ import annotations


class FakeBedrockClient:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def invoke(self, request: dict) -> dict:
        self.requests.append(request)
        return {"ok": True, "request_count": len(self.requests)}

