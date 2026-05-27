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

"""User profile router — includes lazy provisioning on first login."""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from synteles_db.models import Organization, User, UserOrg
from synteles_db.repos.orgs import OrgRepo
from synteles_db.repos.users import UserRepo

from auth import TokenClaims, oidc_auth
from db import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/users/me")
async def get_user_profile(
    claims: Annotated[TokenClaims, Depends(oidc_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    user = await UserRepo(db).get(UUID(claims.user_id))
    if user is None:
        org_id, org_name = await _provision_user(claims, db)
        return {"sub": claims.user_id, "org_id": str(org_id), "org_name": org_name}
    return await _build_profile(claims, db)


async def _provision_user(claims: TokenClaims, db: AsyncSession) -> tuple[UUID, str]:
    """Atomically create user + default org on first login. Returns (org_id, org_name)."""
    from sqlalchemy.exc import IntegrityError

    user_id = UUID(claims.user_id)
    org_id = uuid4()
    org_name = "Personal Workspace"

    try:
        db.add(User(id=user_id, preferences={"home_org_id": str(org_id)}))
        db.add(Organization(id=org_id, name=org_name))
        db.add(UserOrg(user_id=user_id, org_id=org_id))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing_org_id = await UserRepo(db).get_first_org_id(user_id)
        if not existing_org_id:
            raise HTTPException(status_code=500, detail="Provisioning conflict") from None
        org_id = existing_org_id
        org = await OrgRepo(db).get(org_id)
        org_name = org.name if org else org_name

    await _set_keycloak_org_id(claims.user_id, str(org_id))
    return org_id, org_name


async def _set_keycloak_org_id(user_id: str, org_id: str) -> None:
    """Set org_id user attribute in Keycloak via Admin API. No-op if not configured."""
    from config import (
        KEYCLOAK_ADMIN_URL,
        KEYCLOAK_PROVISIONER_CLIENT_ID,
        KEYCLOAK_PROVISIONER_CLIENT_SECRET,
        KEYCLOAK_REALM,
    )

    if not all(
        [KEYCLOAK_ADMIN_URL, KEYCLOAK_PROVISIONER_CLIENT_ID, KEYCLOAK_PROVISIONER_CLIENT_SECRET]
    ):
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_res = await client.post(
                f"{KEYCLOAK_ADMIN_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": KEYCLOAK_PROVISIONER_CLIENT_ID,
                    "client_secret": KEYCLOAK_PROVISIONER_CLIENT_SECRET,
                },
            )
            token_res.raise_for_status()
            admin_token = token_res.json()["access_token"]

            await client.put(
                f"{KEYCLOAK_ADMIN_URL}/admin/realms/{KEYCLOAK_REALM}/users/{user_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"attributes": {"org_id": [org_id]}},
            )
    except Exception as exc:
        logger.warning("Failed to set org_id in Keycloak for user %s: %s", user_id, exc)


async def _build_profile(claims: TokenClaims, db: AsyncSession) -> dict[str, Any]:
    profile: dict[str, Any] = {"sub": claims.user_id}
    try:
        org_id_val = (
            UUID(claims.org_id)
            if claims.org_id
            else await UserRepo(db).get_first_org_id(UUID(claims.user_id))
        )
        if org_id_val:
            profile["org_id"] = str(org_id_val)
            org = await OrgRepo(db).get(org_id_val)
            if org:
                profile["org_name"] = org.name
    except Exception as exc:
        logger.error("DB error fetching org info: %s", exc)
    return profile


async def _fetch_userinfo(token: str) -> dict[str, Any]:
    from config import COGNITO_DOMAIN, OIDC_ISSUER_URL

    url: str | None = None
    if OIDC_ISSUER_URL:
        url = f"{OIDC_ISSUER_URL}/protocol/openid-connect/userinfo"
    elif COGNITO_DOMAIN:
        url = f"https://{COGNITO_DOMAIN}/oauth2/userInfo"

    if not url:
        return {}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            if resp.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid access token")
            resp.raise_for_status()
            return dict(resp.json())
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to fetch userinfo from %s: %s", url, exc)
        return {}


@router.get("/api/users/me/profile")
async def get_user_profile_rich(
    claims: Annotated[TokenClaims, Depends(oidc_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str, __import__("fastapi").Header()],
) -> dict[str, Any]:
    token = authorization.removeprefix("Bearer ").strip()
    userinfo = await _fetch_userinfo(token)
    base = await _build_profile(claims, db)
    return {
        "sub": claims.user_id,
        "email": userinfo.get("email"),
        "name": userinfo.get("name"),
        "given_name": userinfo.get("given_name"),
        "family_name": userinfo.get("family_name"),
        "picture": userinfo.get("picture"),
        **{k: v for k, v in base.items() if k != "sub"},
    }
