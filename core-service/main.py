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

"""core-service: FastAPI application entry point."""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import auth_router
from config import CORS_ALLOWED_ORIGINS
from routers import (
    agentlets,
    agentlets_public,
    apikeys,
    connectors,
    conversations,
    files,
    models,
    orgs,
    secrets,
    users,
)

app = FastAPI(title="core-service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(agentlets.router)
app.include_router(users.router)
app.include_router(orgs.router)
app.include_router(apikeys.router)
app.include_router(agentlets_public.router)
app.include_router(connectors.router)
app.include_router(conversations.router)
app.include_router(models.router)
app.include_router(secrets.router)
app.include_router(files.router)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok"}
