from __future__ import annotations

import pytest

from token_service.identity import IdentityResolutionError, extract_username_from_event, parse_username_from_user_arn


def test_parse_username_from_assumed_role_arn() -> None:
    arn = "arn:aws:sts::123456789012:assumed-role/AWSReservedSSO_Dev/alice@example.com"

    assert parse_username_from_user_arn(arn) == "alice@example.com"


def test_extract_username_from_event() -> None:
    event = {
        "requestContext": {
            "identity": {
                "userArn": "arn:aws:sts::123456789012:assumed-role/AWSReservedSSO_Dev/alice",
            }
        }
    }

    assert extract_username_from_event(event) == "alice"


def test_missing_user_arn_raises_identity_error() -> None:
    with pytest.raises(IdentityResolutionError):
        extract_username_from_event({"requestContext": {"identity": {}}})

