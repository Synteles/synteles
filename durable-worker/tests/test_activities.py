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

"""Unit tests for activities/notify.py."""

from __future__ import annotations

from temporalio.testing import ActivityEnvironment

from activities.notify import notify_resumed, notify_waiting_for_signal


async def test_notify_waiting_for_signal_completes() -> None:
    env = ActivityEnvironment()
    await env.run(notify_waiting_for_signal, "exec-123", "Please approve the contract.")


async def test_notify_waiting_for_signal_empty_question() -> None:
    env = ActivityEnvironment()
    await env.run(notify_waiting_for_signal, "exec-123", "")


async def test_notify_resumed_completes() -> None:
    env = ActivityEnvironment()
    await env.run(notify_resumed, "exec-123")


async def test_notify_resumed_different_execution_id() -> None:
    env = ActivityEnvironment()
    await env.run(notify_resumed, "another-exec-id")
