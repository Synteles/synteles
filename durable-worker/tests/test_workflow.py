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

"""Unit tests for AgentWorkflow signal and query handlers.

These tests exercise the HITL state-machine logic directly on an AgentWorkflow
instance without running a full Temporal worker, which would require a live
Temporal server and an OpenAI API key.
"""

from __future__ import annotations

from workflows.agent import AgentWorkflow

# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_input_needed_is_false() -> None:
    wf = AgentWorkflow()
    assert wf.is_input_needed() is False


def test_initial_pending_question_is_empty() -> None:
    wf = AgentWorkflow()
    assert wf.get_pending_question() == ""


# ---------------------------------------------------------------------------
# provide_user_input signal
# ---------------------------------------------------------------------------


def test_provide_user_input_clears_input_needed() -> None:
    wf = AgentWorkflow()
    wf._input_needed = True
    wf.provide_user_input("approved")
    assert wf.is_input_needed() is False


def test_provide_user_input_stores_text() -> None:
    wf = AgentWorkflow()
    wf.provide_user_input("user answer")
    assert wf._user_input == "user answer"


def test_provide_user_input_with_empty_string() -> None:
    wf = AgentWorkflow()
    wf._input_needed = True
    wf.provide_user_input("")
    assert wf._user_input == ""
    assert wf.is_input_needed() is False


# ---------------------------------------------------------------------------
# is_input_needed query
# ---------------------------------------------------------------------------


def test_is_input_needed_reflects_internal_flag() -> None:
    wf = AgentWorkflow()
    wf._input_needed = True
    assert wf.is_input_needed() is True


def test_is_input_needed_false_after_signal() -> None:
    wf = AgentWorkflow()
    wf._input_needed = True
    wf.provide_user_input("done")
    assert wf.is_input_needed() is False


# ---------------------------------------------------------------------------
# get_pending_question query
# ---------------------------------------------------------------------------


def test_get_pending_question_returns_set_question() -> None:
    wf = AgentWorkflow()
    wf._question = "Should I proceed?"
    assert wf.get_pending_question() == "Should I proceed?"


def test_get_pending_question_empty_after_init() -> None:
    wf = AgentWorkflow()
    assert wf.get_pending_question() == ""


# ---------------------------------------------------------------------------
# State transitions — full ask/answer cycle
# ---------------------------------------------------------------------------


def test_signal_cycle_question_then_answer() -> None:
    """Simulate the ask_user ↔ provide_user_input round-trip at the Python level."""
    wf = AgentWorkflow()

    # Workflow sets up wait state (as ask_user would)
    wf._question = "Please approve the contract."
    wf._input_needed = True

    assert wf.is_input_needed() is True
    assert wf.get_pending_question() == "Please approve the contract."

    # User delivers signal
    wf.provide_user_input("Approved")

    assert wf.is_input_needed() is False
    assert wf._user_input == "Approved"


def test_multiple_signal_cycles() -> None:
    """Second ask_user round works independently of the first."""
    wf = AgentWorkflow()

    wf._question = "First question?"
    wf._input_needed = True
    wf.provide_user_input("First answer")

    # Simulate workflow clearing state between rounds (as ask_user does)
    wf._question = ""
    wf._user_input = ""

    wf._question = "Second question?"
    wf._input_needed = True
    wf.provide_user_input("Second answer")

    assert wf.is_input_needed() is False
    assert wf._user_input == "Second answer"
