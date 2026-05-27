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

"""Unit tests for connectors router validators and formatters."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from routers.connectors import _format_connector, _validate_mcp_config, _validate_name

_NOW = datetime(2025, 6, 1, tzinfo=UTC)


# ─── _validate_name ────────────────────────────────────────────────────────


def test_validate_name_valid() -> None:
    assert _validate_name("my-connector") is None


def test_validate_name_alphanumeric_start() -> None:
    assert _validate_name("A1_connector") is None


def test_validate_name_single_char() -> None:
    assert _validate_name("a") is None


def test_validate_name_max_length() -> None:
    assert _validate_name("a" * 128) is None


def test_validate_name_empty_returns_error() -> None:
    assert _validate_name("") == "name is required"


def test_validate_name_starts_with_underscore_returns_error() -> None:
    assert _validate_name("_bad") is not None


def test_validate_name_starts_with_hyphen_returns_error() -> None:
    assert _validate_name("-bad") is not None


def test_validate_name_too_long_returns_error() -> None:
    assert _validate_name("a" * 129) is not None


def test_validate_name_contains_space_returns_error() -> None:
    assert _validate_name("has space") is not None


# ─── _validate_mcp_config ──────────────────────────────────────────────────


def test_validate_mcp_config_valid() -> None:
    config = '{"mcpServers": {"my-server": {"command": "npx"}}}'
    assert _validate_mcp_config(config) is None


def test_validate_mcp_config_empty_returns_error() -> None:
    assert _validate_mcp_config("") == "mcp_config is required"


def test_validate_mcp_config_invalid_json_returns_error() -> None:
    error = _validate_mcp_config("{not-json}")
    assert error is not None
    assert "not valid JSON" in error


def test_validate_mcp_config_missing_mcp_servers_key_returns_error() -> None:
    error = _validate_mcp_config('{"servers": {}}')
    assert error is not None
    assert "mcpServers" in error


def test_validate_mcp_config_empty_mcp_servers_is_valid() -> None:
    assert _validate_mcp_config('{"mcpServers": {}}') is None


# ─── _format_connector ─────────────────────────────────────────────────────


def test_format_connector_happy_path() -> None:
    c = MagicMock()
    c.name = "my-connector"
    c.config = {"description": "A connector", "mcp_config": '{"mcpServers": {}}'}
    c.created_at = _NOW
    c.updated_at = _NOW

    result = _format_connector(c)

    assert result["name"] == "my-connector"
    assert result["description"] == "A connector"
    assert result["mcp_config"] == '{"mcpServers": {}}'
    assert result["created_at"] == _NOW.isoformat()
    assert result["updated_at"] == _NOW.isoformat()


def test_format_connector_missing_config_defaults_to_empty() -> None:
    c = MagicMock()
    c.name = "bare"
    c.config = None
    c.created_at = _NOW
    c.updated_at = _NOW

    result = _format_connector(c)

    assert result["description"] == ""
    assert result["mcp_config"] == ""
