from __future__ import annotations

import hashlib
import secrets

VIRTUAL_KEY_PREFIX = "vk_"
VIRTUAL_KEY_TOKEN_BYTES = 24
VISIBLE_KEY_PREFIX_LENGTH = 12


def generate_virtual_key() -> str:
    token = secrets.token_urlsafe(VIRTUAL_KEY_TOKEN_BYTES)
    return f"{VIRTUAL_KEY_PREFIX}{token}"


def hash_virtual_key(virtual_key: str) -> str:
    return hashlib.sha256(virtual_key.encode("utf-8")).hexdigest()


def get_virtual_key_prefix(virtual_key: str) -> str:
    return virtual_key[:VISIBLE_KEY_PREFIX_LENGTH]

