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

"""Unit tests for worker.py startup validation."""

from __future__ import annotations

from unittest.mock import patch

import pytest


async def test_main_raises_when_manifest_url_missing() -> None:
    with patch("worker.SYNTELES_MANIFEST_URL", ""):
        with pytest.raises(RuntimeError, match="SYNTELES_MANIFEST_URL"):
            from worker import main

            await main()


async def test_main_raises_when_task_queue_missing() -> None:
    with (
        patch("worker.SYNTELES_MANIFEST_URL", "http://example.com/manifest.json"),
        patch("worker.TEMPORAL_TASK_QUEUE", ""),
    ):
        with pytest.raises(RuntimeError, match="TEMPORAL_TASK_QUEUE"):
            from worker import main

            await main()


async def test_main_raises_when_execution_id_missing() -> None:
    with (
        patch("worker.SYNTELES_MANIFEST_URL", "http://example.com/manifest.json"),
        patch("worker.TEMPORAL_TASK_QUEUE", "my-queue"),
        patch("worker.EXECUTION_ID", ""),
    ):
        with pytest.raises(RuntimeError, match="EXECUTION_ID"):
            from worker import main

            await main()
