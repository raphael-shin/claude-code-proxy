from __future__ import annotations

from security.encryption import ENCRYPTION_PREFIX


class FakeEncryptionService:
    def __init__(self) -> None:
        self.encrypt_calls: list[str] = []
        self.decrypt_calls: list[str] = []

    def encrypt(self, plaintext: str) -> str:
        self.encrypt_calls.append(plaintext)
        return f"{ENCRYPTION_PREFIX}{plaintext}"

    def decrypt(self, ciphertext: str) -> str:
        self.decrypt_calls.append(ciphertext)
        return ciphertext.removeprefix(ENCRYPTION_PREFIX)

