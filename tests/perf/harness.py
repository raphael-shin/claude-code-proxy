from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from time import perf_counter
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class ProbeResult:
    samples_ms: tuple[float, ...]

    @property
    def max_ms(self) -> float:
        return max(self.samples_ms, default=0.0)

    @property
    def p95_ms(self) -> float:
        if not self.samples_ms:
            return 0.0
        ordered = sorted(self.samples_ms)
        index = max(0, ceil(len(ordered) * 0.95) - 1)
        return ordered[index]


def run_probe(
    target: Callable[[], T],
    *,
    warmups: int,
    sample_size: int,
) -> tuple[ProbeResult, list[T]]:
    for _ in range(max(0, warmups)):
        target()

    samples_ms: list[float] = []
    results: list[T] = []
    for _ in range(sample_size):
        started_at = perf_counter()
        results.append(target())
        samples_ms.append((perf_counter() - started_at) * 1000)
    return ProbeResult(samples_ms=tuple(samples_ms)), results
