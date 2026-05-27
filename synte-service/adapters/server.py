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

"""FastAPI adapter — Synte Engine (Docker Compose, ECS Fargate)."""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
from jwt import PyJWKClient

from core.protocol import format_sse
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="chat-stream")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


# ── JWT validation ────────────────────────────────────────────────────────────

_JWKS_CLIENT: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient | None:
    global _JWKS_CLIENT
    issuer_url = os.environ.get("OIDC_ISSUER_URL", "")
    jwks_url = os.environ.get("OIDC_JWKS_URL", "")
    if not issuer_url and not jwks_url:
        return None
    if _JWKS_CLIENT is None:
        effective_url = jwks_url or f"{issuer_url}/protocol/openid-connect/certs"
        _JWKS_CLIENT = PyJWKClient(effective_url, cache_keys=True)
    return _JWKS_CLIENT


def _extract_token(authorization: Annotated[str, Header()]) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    client = _get_jwks_client()
    if client is None:
        return token  # local dev without OIDC — skip signature check
    try:
        signing_key = client.get_signing_key_from_jwt(token)
        jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


# ── Models / streaming ────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    messages: list[dict] = []
    manager_state: dict = {}
    org_id: str | None = None
    pending_input_objects: list[str] | None = None


async def _sse_stream(req: ChatRequest, access_token: str) -> AsyncGenerator[bytes, None]:
    from core.agent import stream_turn  # lazy import: avoids loading strands/litellm at module level
    async for event in stream_turn(
        message=req.message,
        messages=req.messages,
        manager_state=req.manager_state,
        access_token=access_token,
        org_id=req.org_id,
        pending_input_objects=req.pending_input_objects,
    ):
        yield format_sse(event)


def _streaming_response(req: ChatRequest, access_token: str) -> StreamingResponse:
    return StreamingResponse(
        _sse_stream(req, access_token),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Routes ────────────────────────────────────────────────────────────────────

Token = Annotated[str, Depends(_extract_token)]


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, access_token: Token) -> StreamingResponse:
    """ECS Fargate / local dev entry point."""
    return _streaming_response(req, access_token)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
