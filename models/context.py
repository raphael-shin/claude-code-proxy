from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserContext:
    user_id: str
    email: str | None = None
    groups: tuple[str, ...] = ()
    department: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "groups", tuple(self.groups))


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str
    user: UserContext | None = None


@dataclass(frozen=True, slots=True)
class AuthenticatedRequestContext:
    request: RequestContext
    virtual_key_id: str
    key_hash: str
    key_prefix: str

    @property
    def request_id(self) -> str:
        return self.request.request_id

    @property
    def user(self) -> UserContext:
        assert self.request.user is not None
        return self.request.user
