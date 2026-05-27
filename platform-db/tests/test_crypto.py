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

"""Unit tests for AES-256-GCM encrypt/decrypt."""

from __future__ import annotations

import pytest

import synteles_db.crypto as crypto_module
from synteles_db.crypto import decrypt, encrypt

_VALID_KEY = "deadbeef" * 8  # 64 hex chars = 32 bytes


@pytest.fixture(autouse=True)
def reset_key(monkeypatch):
    monkeypatch.setattr(crypto_module, "_SECRET_KEY", None)
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", _VALID_KEY)


def test_encrypt_returns_bytes_tuple():
    nonce, ct = encrypt({"key": "value"})
    assert isinstance(nonce, bytes)
    assert isinstance(ct, bytes)


def test_encrypt_nonce_is_12_bytes():
    nonce, _ = encrypt({"key": "value"})
    assert len(nonce) == 12


def test_decrypt_roundtrip():
    original = {"api_key": "secret-123", "token": "abc"}
    nonce, ct = encrypt(original)
    assert decrypt(nonce, ct) == original


def test_decrypt_roundtrip_multiple_keys():
    original = {"KEY_A": "val1", "KEY_B": "val2", "KEY_C": "val3"}
    nonce, ct = encrypt(original)
    assert decrypt(nonce, ct) == original


def test_encrypt_produces_unique_nonces():
    nonce1, _ = encrypt({"k": "v"})
    nonce2, _ = encrypt({"k": "v"})
    assert nonce1 != nonce2


def test_decrypt_tampered_ciphertext_raises():
    nonce, ct = encrypt({"k": "v"})
    tampered = bytes([ct[0] ^ 0xFF]) + ct[1:]
    with pytest.raises(ValueError):
        decrypt(nonce, tampered)


def test_decrypt_tampered_nonce_raises():
    nonce, ct = encrypt({"k": "v"})
    bad_nonce = bytes([nonce[0] ^ 0xFF]) + nonce[1:]
    with pytest.raises(ValueError):
        decrypt(bad_nonce, ct)


def test_key_missing_raises(monkeypatch):
    monkeypatch.setattr(crypto_module, "_SECRET_KEY", None)
    monkeypatch.delenv("SECRET_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_ENCRYPTION_KEY env var is required"):
        encrypt({"k": "v"})


def test_key_invalid_hex_raises(monkeypatch):
    monkeypatch.setattr(crypto_module, "_SECRET_KEY", None)
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", "not-valid-hex!!")
    with pytest.raises(RuntimeError, match="64-char hex string"):
        encrypt({"k": "v"})


def test_key_wrong_length_raises(monkeypatch):
    monkeypatch.setattr(crypto_module, "_SECRET_KEY", None)
    monkeypatch.setenv("SECRET_ENCRYPTION_KEY", "deadbeef" * 4)  # 32 hex chars = 16 bytes
    with pytest.raises(RuntimeError, match="32 bytes"):
        encrypt({"k": "v"})
