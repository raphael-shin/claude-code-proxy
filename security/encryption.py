from __future__ import annotations

import base64
from typing import Protocol, runtime_checkable

ENCRYPTION_PREFIX = "enc::"


@runtime_checkable
class EncryptionService(Protocol):
    def encrypt(self, plaintext: str) -> str: ...

    def decrypt(self, ciphertext: str) -> str: ...


class SimpleEnvelopeEncryption:
    def encrypt(self, plaintext: str) -> str:
        encoded = base64.urlsafe_b64encode(plaintext.encode("utf-8")).decode("ascii")
        return f"{ENCRYPTION_PREFIX}{encoded}"

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext.startswith(ENCRYPTION_PREFIX):
            raise ValueError("Encrypted value is missing the expected prefix.")
        encoded = ciphertext.removeprefix(ENCRYPTION_PREFIX)
        return base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")

