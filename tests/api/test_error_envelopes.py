from __future__ import annotations

import json

import pytest

from api.errors import error_response_for_exception
from models.errors import (
    access_denied_error,
    authentication_failed_error,
    rate_limit_exceeded_error,
)
from proxy.bedrock_converse.request_builder import BedrockRequestBuildError


@pytest.mark.parametrize(
    ("error", "status_code", "error_type", "details"),
    [
        (
            authentication_failed_error(
                "req-auth-envelope",
                details={"reason": "missing_bearer_token"},
            ),
            401,
            "authentication_error",
            {"reason": "missing_bearer_token"},
        ),
        (
            access_denied_error(
                "req-permission-envelope",
                message="Request blocked by policy: model_denied.",
            ),
            403,
            "permission_error",
            None,
        ),
        (
            rate_limit_exceeded_error(
                "req-rate-limit-envelope",
                headers={"Retry-After": "7"},
            ),
            429,
            "rate_limit_error",
            None,
        ),
        (
            BedrockRequestBuildError(
                reason="invalid_content",
                message="Message content must be a string or list of blocks.",
            ),
            400,
            "invalid_request_error",
            {"reason": "invalid_content"},
        ),
        (
            RuntimeError("bedrock upstream unavailable"),
            502,
            "api_error",
            {"reason": "RuntimeError"},
        ),
    ],
)
def test_error_response_for_exception_maps_to_anthropic_envelopes(
    error: Exception,
    status_code: int,
    error_type: str,
    details: dict[str, str] | None,
) -> None:
    response = error_response_for_exception(error, request_id="req-fallback")
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == status_code
    assert payload["type"] == "error"
    assert payload["error"]["type"] == error_type
    if details is None:
        assert "details" not in payload["error"]
    else:
        assert payload["error"]["details"] == details


def test_rate_limit_mapping_preserves_retry_after_header() -> None:
    response = error_response_for_exception(
        rate_limit_exceeded_error(
            "req-rate-limit-headers",
            headers={"Retry-After": "13"},
        ),
        request_id="req-rate-limit-headers",
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "13"
