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

"""Unit tests for secrets router — _validate_name."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from routers.secrets import _validate_name


def test_validate_name_valid_simple() -> None:
    _validate_name("my-secret")  # must not raise


def test_validate_name_valid_alphanumeric_start() -> None:
    _validate_name("A1_KEY")


def test_validate_name_valid_max_length() -> None:
    _validate_name("a" * 128)


def test_validate_name_empty_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_name("")
    assert exc_info.value.status_code == 400


def test_validate_name_starts_with_underscore_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_name("_SECRET")
    assert exc_info.value.status_code == 400


def test_validate_name_starts_with_hyphen_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_name("-secret")
    assert exc_info.value.status_code == 400


def test_validate_name_too_long_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_name("a" * 129)
    assert exc_info.value.status_code == 400


def test_validate_name_reserved_default_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_name("default")
    assert exc_info.value.status_code == 400
    assert "reserved" in exc_info.value.detail.lower()


def test_validate_name_contains_space_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _validate_name("has space")
    assert exc_info.value.status_code == 400
