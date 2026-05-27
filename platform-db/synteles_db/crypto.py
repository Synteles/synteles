# Copyright 2026 Emin Askerov
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""AES-256-GCM encrypt/decrypt for user secrets stored in PostgreSQL."""

from __future__ import annotations

import json
import os
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_SECRET_KEY: bytes | None = None


def _key() -> bytes:
    global _SECRET_KEY
    if _SECRET_KEY is None:
        raw_hex = os.environ.get("SECRET_ENCRYPTION_KEY", "")
        if not raw_hex:
            raise RuntimeError("SECRET_ENCRYPTION_KEY env var is required")
        try:
            key = bytes.fromhex(raw_hex)
        except ValueError as exc:
            raise RuntimeError("SECRET_ENCRYPTION_KEY must be a 64-char hex string") from exc
        if len(key) != 32:
            raise RuntimeError(
                f"SECRET_ENCRYPTION_KEY must be 32 bytes (64 hex chars), got {len(key)}"
            )
        _SECRET_KEY = key
    return _SECRET_KEY


def encrypt(plaintext: dict[str, Any]) -> tuple[bytes, bytes]:
    """Return (nonce, ciphertext). nonce is 12 random bytes; ciphertext includes GCM auth tag."""
    nonce = os.urandom(12)
    ct = AESGCM(_key()).encrypt(nonce, json.dumps(plaintext).encode(), None)
    return nonce, ct


def decrypt(nonce: bytes, ciphertext: bytes) -> dict[str, Any]:
    """Decrypt and return the original dict. Raises ValueError on tampered data."""
    try:
        raw = AESGCM(_key()).decrypt(nonce, ciphertext, None)
    except InvalidTag as exc:
        raise ValueError("Decryption failed: tampered data") from exc
    result: dict[str, Any] = json.loads(raw)
    return result
