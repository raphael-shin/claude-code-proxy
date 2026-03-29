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

