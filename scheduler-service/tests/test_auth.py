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

"""Unit tests for auth.py — trusted_claims dependency."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from auth import TokenClaims, trusted_claims


async def test_trusted_claims_returns_token_claims() -> None:
    result = await trusted_claims(x_user_id="u-123", x_org_id="o-abc")
    assert isinstance(result, TokenClaims)
    assert result.user_id == "u-123"
    assert result.org_id == "o-abc"


async def test_trusted_claims_missing_user_id_raises_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await trusted_claims(x_user_id=None, x_org_id="o-abc")
    assert exc_info.value.status_code == 401


async def test_trusted_claims_empty_user_id_raises_401() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await trusted_claims(x_user_id="", x_org_id="o-abc")
    assert exc_info.value.status_code == 401


async def test_trusted_claims_empty_org_id_returns_none() -> None:
    result = await trusted_claims(x_user_id="u-123", x_org_id="")
    assert result.org_id is None


async def test_trusted_claims_no_org_id_returns_none() -> None:
    result = await trusted_claims(x_user_id="u-123", x_org_id=None)
    assert result.org_id is None
