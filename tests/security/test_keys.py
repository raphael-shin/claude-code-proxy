from __future__ import annotations

from security.keys import VIRTUAL_KEY_PREFIX, generate_virtual_key, get_virtual_key_prefix, hash_virtual_key


def test_generate_virtual_key_uses_expected_prefix() -> None:
    assert generate_virtual_key().startswith(VIRTUAL_KEY_PREFIX)


def test_hash_virtual_key_is_deterministic() -> None:
    assert hash_virtual_key("vk_same") == hash_virtual_key("vk_same")


def test_virtual_key_prefix_helper_is_stable() -> None:
    assert get_virtual_key_prefix("vk_1234567890abcdef") == "vk_123456789"

