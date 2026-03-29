from __future__ import annotations

from typing import Any, Mapping

from models.context import AuthenticatedRequestContext
from models.domain import VirtualKeyStatus
from models.errors import ServiceError, authentication_failed_error
from repositories.user_repository import UserRepository
from repositories.virtual_key_repository import VirtualKeyAuthRepository
from security.keys import VIRTUAL_KEY_PREFIX, hash_virtual_key

from proxy.context import restore_trusted_request_context

AUTH_REASON_MISSING_BEARER = "missing_bearer_token"
AUTH_REASON_MALFORMED_BEARER = "malformed_bearer_token"
AUTH_REASON_UNKNOWN_KEY = "unknown_virtual_key"
AUTH_REASON_INACTIVE_KEY = "inactive_virtual_key"
AUTH_REASON_ORPHANED_KEY = "orphaned_virtual_key"


class ProxyAuthService:
    def __init__(
        self,
        *,
        virtual_key_repository: VirtualKeyAuthRepository,
        user_repository: UserRepository,
    ) -> None:
        self._virtual_key_repository = virtual_key_repository
        self._user_repository = user_repository

    def authenticate(
        self,
        authorization_header: str | None,
        *,
        request_id: str,
        headers: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> AuthenticatedRequestContext:
        virtual_key = self._extract_virtual_key(authorization_header, request_id=request_id)
        key_hash = hash_virtual_key(virtual_key)
        record = self._virtual_key_repository.get_key_by_hash(key_hash)
        if record is None:
            raise self._authentication_error(request_id, AUTH_REASON_UNKNOWN_KEY)
        if record.status is not VirtualKeyStatus.ACTIVE:
            raise self._authentication_error(request_id, AUTH_REASON_INACTIVE_KEY)

        user = self._user_repository.get_user(record.user_id)
        if user is None:
            raise self._authentication_error(request_id, AUTH_REASON_ORPHANED_KEY)

        return restore_trusted_request_context(
            request_id=request_id,
            user=user,
            virtual_key_id=record.id,
            key_hash=record.key_hash,
            key_prefix=record.key_prefix,
            untrusted_headers=headers,
            untrusted_body=body,
        )

    def _extract_virtual_key(self, authorization_header: str | None, *, request_id: str) -> str:
        if authorization_header is None or not authorization_header.strip():
            raise self._authentication_error(request_id, AUTH_REASON_MISSING_BEARER)

        scheme, separator, token = authorization_header.partition(" ")
        if separator != " " or scheme != "Bearer" or not token.strip():
            raise self._authentication_error(request_id, AUTH_REASON_MALFORMED_BEARER)
        normalized_token = token.strip()
        if not normalized_token.startswith(VIRTUAL_KEY_PREFIX):
            raise self._authentication_error(request_id, AUTH_REASON_MALFORMED_BEARER)
        return normalized_token

    @staticmethod
    def _authentication_error(request_id: str, reason: str) -> ServiceError:
        return authentication_failed_error(
            request_id,
            details={"reason": reason},
        )
