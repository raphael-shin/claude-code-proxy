from __future__ import annotations


class IdentityResolutionError(ValueError):
    pass


def _extract_identity_section(event: dict) -> dict:
    request_context = event.get("requestContext")
    if not isinstance(request_context, dict):
        raise IdentityResolutionError("API Gateway requestContext is missing.")
    identity = request_context.get("identity")
    if not isinstance(identity, dict):
        raise IdentityResolutionError("API Gateway requestContext.identity is missing.")
    return identity


def extract_user_arn(event: dict) -> str:
    identity = _extract_identity_section(event)
    user_arn = identity.get("userArn")
    if not isinstance(user_arn, str) or not user_arn.strip():
        raise IdentityResolutionError("API Gateway requestContext.identity.userArn is missing.")
    return user_arn


def parse_username_from_user_arn(user_arn: str) -> str:
    username = user_arn.rsplit("/", 1)[-1].strip()
    if not username or username == user_arn:
        raise IdentityResolutionError(f"Could not parse username from user ARN: {user_arn}")
    return username


def extract_username_from_event(event: dict) -> str:
    return parse_username_from_user_arn(extract_user_arn(event))

