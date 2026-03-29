from __future__ import annotations

from models.domain import IdentityMapping, UserRecord, VirtualKeyRecord


class FakePostgresConnection:
    def __init__(self) -> None:
        self.users: dict[str, UserRecord] = {}
        self.identity_mappings: dict[str, IdentityMapping] = {}
        self.virtual_keys: dict[str, VirtualKeyRecord] = {}
        self.operations: list[tuple[str, str]] = []

    def seed_user(self, user: UserRecord, *, username: str | None = None) -> None:
        self.users[user.id] = user
        if username is not None:
            self.seed_identity_mapping(IdentityMapping(username=username, user_id=user.id))

    def seed_identity_mapping(self, mapping: IdentityMapping) -> None:
        self.identity_mappings[mapping.username] = mapping

    def seed_virtual_key(self, record: VirtualKeyRecord) -> None:
        self.virtual_keys[record.id] = record

    def get_identity_mapping(self, username: str) -> IdentityMapping | None:
        self.operations.append(("get_identity_mapping", username))
        return self.identity_mappings.get(username)

    def get_user(self, user_id: str) -> UserRecord | None:
        self.operations.append(("get_user", user_id))
        return self.users.get(user_id)

    def list_virtual_keys_for_user(self, user_id: str) -> list[VirtualKeyRecord]:
        self.operations.append(("list_virtual_keys_for_user", user_id))
        return [record for record in self.virtual_keys.values() if record.user_id == user_id]

    def save_virtual_key(self, record: VirtualKeyRecord) -> None:
        self.operations.append(("save_virtual_key", record.id))
        self.virtual_keys[record.id] = record

