from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import AppDependencies
from tests.api.runtime_stubs import ReadyCheck


def test_health_is_always_ok() -> None:
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reflects_dependency_health() -> None:
    ready_app = create_app(
        AppDependencies(
            readiness_checks=(ReadyCheck(True), ReadyCheck(True)),
        )
    )
    not_ready_app = create_app(
        AppDependencies(
            readiness_checks=(ReadyCheck(True), ReadyCheck(False)),
        )
    )

    ready_response = TestClient(ready_app).get("/ready")
    not_ready_response = TestClient(not_ready_app).get("/ready")

    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ready"}
    assert not_ready_response.status_code == 503
    assert not_ready_response.json() == {"status": "not_ready"}
