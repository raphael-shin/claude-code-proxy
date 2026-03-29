from __future__ import annotations


class FakeRequestIdGenerator:
    def __init__(self, *values: str) -> None:
        self._values = list(values) or ["req-1"]
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.calls <= len(self._values):
            return self._values[self.calls - 1]
        return f"req-{self.calls}"

