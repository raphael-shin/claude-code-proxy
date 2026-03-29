from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Mapping, Protocol

from fastapi import FastAPI, Request

RUNTIME_REQUEST_COUNT_METRIC = "runtime.requests"
RUNTIME_REQUEST_ERROR_COUNT_METRIC = "runtime.errors"
RUNTIME_REQUEST_LATENCY_METRIC = "runtime.request_latency_ms"

RUNTIME_FAILURE_EVENT = "runtime_request_failed"
RUNTIME_LOGGER_NAME = "claude_code_proxy.runtime"
REQUEST_ID_HEADER = "X-Request-Id"

logger = logging.getLogger(RUNTIME_LOGGER_NAME)


class RuntimeMetricsRecorder(Protocol):
    def increment(
        self,
        name: str,
        *,
        value: int = 1,
        tags: Mapping[str, str] | None = None,
    ) -> None: ...

    def observe(
        self,
        name: str,
        value: float,
        *,
        tags: Mapping[str, str] | None = None,
    ) -> None: ...


def resolve_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if isinstance(request_id, str) and request_id.strip():
        return request_id

    request_id = request.app.state.dependencies.request_id_generator()
    request.state.request_id = request_id
    return request_id


def install_runtime_observability(app: FastAPI) -> None:
    @app.middleware("http")
    async def runtime_observability_middleware(request: Request, call_next):
        request_id = resolve_request_id(request)
        started_at = perf_counter()
        response = await call_next(request)
        latency_ms = int((perf_counter() - started_at) * 1000)
        tags = {
            "method": request.method,
            "path": request.url.path,
            "status_code": str(response.status_code),
        }
        _record_metrics(app, latency_ms=latency_ms, response_status=response.status_code, tags=tags)
        if response.status_code >= 400:
            logger.warning(
                json.dumps(
                    {
                        "event": RUNTIME_FAILURE_EVENT,
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                    },
                    sort_keys=True,
                )
            )
        response.headers.setdefault(REQUEST_ID_HEADER, request_id)
        return response


def _record_metrics(
    app: FastAPI,
    *,
    latency_ms: int,
    response_status: int,
    tags: Mapping[str, str],
) -> None:
    recorder = getattr(app.state.dependencies, "runtime_metrics", None)
    if recorder is None:
        return

    recorder.increment(RUNTIME_REQUEST_COUNT_METRIC, tags=tags)
    recorder.observe(RUNTIME_REQUEST_LATENCY_METRIC, float(latency_ms), tags=tags)
    if response_status >= 400:
        recorder.increment(RUNTIME_REQUEST_ERROR_COUNT_METRIC, tags=tags)
