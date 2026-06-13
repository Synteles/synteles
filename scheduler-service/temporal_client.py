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

"""Shared lazy-singleton Temporal client.

Opens a single gRPC connection on first use and reuses it for all callers
(DockerDurableBackend, signal/status routers). Avoids reconnecting on every
monitor tick or request.
"""

from __future__ import annotations

import asyncio

from temporalio.client import Client

from config import TEMPORAL_ADDRESS

_client: Client | None = None
_lock = asyncio.Lock()


async def get_temporal_client() -> Client:
    global _client
    if _client is None:
        async with _lock:
            if _client is None:
                _client = await Client.connect(TEMPORAL_ADDRESS)
    return _client
