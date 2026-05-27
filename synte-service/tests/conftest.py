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

"""Shared pytest fixtures for the chat-stream service test suite.

Env vars are set at module level before any service imports so that
module-level singletons (e.g. _JWKS_CLIENT) initialise with test values.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

# ── Set environment variables before any service code is imported ────────────
os.environ.setdefault("COGNITO_USER_POOL_ID", "us-east-1_TESTPOOL")
os.environ.setdefault("CHAT_MODEL_ID", "azure_ai/test-model")
os.environ.setdefault("PORTAL_DOMAIN_NAME", "https://test.synteles.dev")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("API_BASE_URL", "https://api.test.synteles.dev/v1")


# ── mock_context fixture ─────────────────────────────────────────────────────

class _FakeStream:
    """Minimal response-stream object — records every write() call."""

    def __init__(self, writes: list[bytes]) -> None:
        self._writes = writes

    def write(self, data: bytes) -> None:
        self._writes.append(data)


@pytest.fixture
def mock_context():
    """Return (context_mock, writes_list).

    ``context_mock.response_stream`` is a real context manager that yields
    a ``_FakeStream``.  Each ``stream.write(data)`` call appends *data* to
    *writes_list* so tests can inspect what was streamed.
    """
    writes: list[bytes] = []

    @contextmanager
    def fake_response_stream(content_type: str = "text/event-stream"):
        yield _FakeStream(writes)

    ctx = MagicMock()
    ctx.response_stream = fake_response_stream
    return ctx, writes


# ── reset_jwks_client autouse fixture ────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_jwks_client():
    """Reset the JWKS singleton and bypass JWT validation for every test."""
    import adapters.server as mod

    mod._JWKS_CLIENT = None

    # Provide a mock JWKS client and a passthrough jwt.decode so that any
    # Bearer token is accepted without a real Cognito round-trip.
    mock_signing_key = MagicMock()
    mock_signing_key.key = "test-key"
    mock_jwks = MagicMock()
    mock_jwks.get_signing_key_from_jwt.return_value = mock_signing_key

    with patch.object(mod, "_get_jwks_client", return_value=mock_jwks), \
         patch("adapters.server.jwt.decode", return_value={"token_use": "access"}):
        yield

    mod._JWKS_CLIENT = None
