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

"""Authentication helpers for scheduler-service.

Auth is performed exclusively by the API gateway (Traefik → core-service/auth/verify).
This service only reads the identity headers injected by the gateway.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException


@dataclass
class TokenClaims:
    user_id: str
    org_id: str | None


async def trusted_claims(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_org_id: Annotated[str | None, Header(alias="X-Org-Id")] = None,
) -> TokenClaims:
    """Extract identity from Traefik-injected headers. No auth logic — trust the gateway."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return TokenClaims(user_id=x_user_id, org_id=x_org_id or None)


async def trusted_claims_with_org(
    claims: Annotated[TokenClaims, Depends(trusted_claims)],
) -> TokenClaims:
    """Like trusted_claims, but also requires org_id — rejects unprovisioned users with 401."""
    if not claims.org_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return claims
