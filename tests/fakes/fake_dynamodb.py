from __future__ import annotations

from typing import Any, Mapping


class FakeDynamoDbTable:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}
        self.operations: list[tuple[str, str]] = []

    def get_item(self, user_id: str) -> Mapping[str, Any] | None:
        self.operations.append(("get_item", user_id))
        item = self.items.get(user_id)
        if item is None:
            return None
        return dict(item)

    def put_item(self, item: Mapping[str, Any]) -> None:
        user_id = str(item["user_id"])
        self.operations.append(("put_item", user_id))
        self.items[user_id] = dict(item)

    def delete_item(self, user_id: str) -> None:
        self.operations.append(("delete_item", user_id))
        self.items.pop(user_id, None)

