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

"""Tests for agents/agent_creator.py — agent_creator_assistant @tool function."""

from __future__ import annotations

from agents.agent_creator import (
    _MAX_VALIDATION_RETRIES,
    agent_creator_assistant,
)

# ── Minimal valid YAML that validate_yaml returns "VALID" for ─────────────────

_VALID_YAML = """\
agentlet:
  name: test-agent
  version: "1.0.0"
system_prompt: "You are a helpful assistant."
model:
  provider: azure_ai
  model_id: gpt-4o
prompt: "Do the task."
"""

# ── PLATFORM_DEFAULT_MODELS fixture for tests ─────────────────────────────────

_FAKE_PLATFORM_DEFAULTS = [
    {
        "id": "platform_test",
        "label": "Test Model",
        "provider": "azure_ai",
        "model_id": "gpt-5.3-chat",
        "secret_name": "azure_ai",
        "description": "Test platform default.",
        "default_temperature": 1.0,
        "min_temperature": 1.0,
        "is_platform_default": True,
        "secret_literal": "default",
    },
    {
        "id": "platform_cheap",
        "label": "Cheap Model",
        "provider": "bedrock",
        "model_id": "amazon.nova-micro-v1:0",
        "secret_name": "bedrock",
        "description": "A cheap model.",
        "default_temperature": 0.7,
        "is_platform_default": True,
        "secret_literal": "default",
    },
]


def _make_mock_agent_cls(mocker, return_value: str = _VALID_YAML):
    """Patch Agent and LiteLLMModel so agent_creator_assistant never calls real APIs."""
    mock_agent_instance = mocker.MagicMock()
    mock_agent_instance.return_value = return_value
    mock_agent_cls = mocker.patch("agents.agent_creator.Agent", return_value=mock_agent_instance)
    mocker.patch("agents.agent_creator.LiteLLMModel")
    return mock_agent_cls, mock_agent_instance


# ── Basic invocation ──────────────────────────────────────────────────────────


class TestAgentCreatorBasic:
    def test_returns_yaml_string_when_valid(self, mocker):
        _mock_agent_cls, _mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - all good")

        result = agent_creator_assistant("Create a simple agent")

        assert isinstance(result, str)
        assert result == _VALID_YAML

    def test_agent_called_with_query_plus_context(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent X")

        assert mock_agent_instance.called
        call_arg = mock_agent_instance.call_args[0][0]
        assert "Create agent X" in call_arg

    def test_context_note_always_includes_platform_defaults_table(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create an agent")

        call_arg = mock_agent_instance.call_args[0][0]
        assert "PLATFORM DEFAULT MODELS" in call_arg

    def test_litellm_model_constructed(self, mocker):
        _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")
        mock_llm = mocker.patch("agents.agent_creator.LiteLLMModel")

        agent_creator_assistant("Create an agent")

        mock_llm.assert_called_once()


# ── Platform default detection → forces "default" secret ─────────────────────


class TestAgentCreatorPlatformDefaultForcesSecret:
    def test_platform_default_model_adds_default_to_secrets(self, mocker):
        mocker.patch(
            "agents.agent_creator.PLATFORM_DEFAULT_MODELS",
            _FAKE_PLATFORM_DEFAULTS,
        )
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        # gpt-5.3-chat is in _FAKE_PLATFORM_DEFAULTS → "default" should be forced
        agent_creator_assistant(
            "Create agent",
            model_provider="azure_ai",
            model_id="gpt-5.3-chat",
            available_secrets=None,
        )

        call_arg = mock_agent_instance.call_args[0][0]
        # The context note should mention available secrets including "default"
        assert "default" in call_arg

    def test_platform_default_appends_default_when_secrets_exist(self, mocker):
        mocker.patch(
            "agents.agent_creator.PLATFORM_DEFAULT_MODELS",
            _FAKE_PLATFORM_DEFAULTS,
        )
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant(
            "Create agent",
            model_provider="azure_ai",
            model_id="gpt-5.3-chat",
            available_secrets=["anthropic-keys"],
        )

        call_arg = mock_agent_instance.call_args[0][0]
        assert "default" in call_arg
        assert "anthropic-keys" in call_arg

    def test_non_platform_default_does_not_add_default_secret(self, mocker):
        mocker.patch(
            "agents.agent_creator.PLATFORM_DEFAULT_MODELS",
            _FAKE_PLATFORM_DEFAULTS,
        )
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        # my-custom-model is NOT in platform defaults
        agent_creator_assistant(
            "Create agent",
            model_provider="anthropic",
            model_id="my-custom-model",
            available_secrets=["anthropic-keys"],
        )

        call_arg = mock_agent_instance.call_args[0][0]
        # "default" should only appear in table context, not in forced secrets list
        # Check that the secrets note only mentions anthropic-keys
        assert "anthropic-keys" in call_arg


# ── Temperature clamping ──────────────────────────────────────────────────────


class TestAgentCreatorTemperatureClamped:
    def test_temperature_below_min_is_clamped(self, mocker):
        mocker.patch(
            "agents.agent_creator.PLATFORM_DEFAULT_MODELS",
            _FAKE_PLATFORM_DEFAULTS,
        )
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        # gpt-5.3-chat has min_temperature=1.0; pass 0.3 → should be clamped to 1.0
        agent_creator_assistant(
            "Create agent",
            model_provider="azure_ai",
            model_id="gpt-5.3-chat",
            temperature=0.3,
        )

        call_arg = mock_agent_instance.call_args[0][0]
        # The context note should contain "temperature: 1.0" (clamped)
        assert "1.0" in call_arg or "temperature: 1" in call_arg

    def test_temperature_above_min_not_changed(self, mocker):
        mocker.patch(
            "agents.agent_creator.PLATFORM_DEFAULT_MODELS",
            _FAKE_PLATFORM_DEFAULTS,
        )
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        # Pass temperature=1.5 which is above min_temperature=1.0 → unchanged
        agent_creator_assistant(
            "Create agent",
            model_provider="azure_ai",
            model_id="gpt-5.3-chat",
            temperature=1.5,
        )

        call_arg = mock_agent_instance.call_args[0][0]
        assert "1.5" in call_arg

    def test_no_min_temperature_field_means_no_clamping(self, mocker):
        mocker.patch(
            "agents.agent_creator.PLATFORM_DEFAULT_MODELS",
            _FAKE_PLATFORM_DEFAULTS,
        )
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        # amazon.nova-micro-v1:0 has no min_temperature → temperature=0.1 unchanged
        agent_creator_assistant(
            "Create agent",
            model_provider="bedrock",
            model_id="amazon.nova-micro-v1:0",
            temperature=0.1,
        )

        call_arg = mock_agent_instance.call_args[0][0]
        assert "0.1" in call_arg


# ── Input/output format instructions ─────────────────────────────────────────


class TestAgentCreatorInputFormat:
    def test_csv_input_format_includes_dictreader(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent", input_format="csv")

        call_arg = mock_agent_instance.call_args[0][0]
        assert "DictReader" in call_arg or "csv" in call_arg.lower()

    def test_csv_input_format_mentions_tmp_input(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent", input_format="csv")

        call_arg = mock_agent_instance.call_args[0][0]
        assert "/tmp/input/" in call_arg

    def test_mixed_input_format_mentions_mixed_file_types(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent", input_format="mixed")

        call_arg = mock_agent_instance.call_args[0][0]
        assert "mixed" in call_arg.lower()

    def test_xlsx_input_format_mentions_openpyxl(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent", input_format="xlsx")

        call_arg = mock_agent_instance.call_args[0][0]
        assert "openpyxl" in call_arg

    def test_no_input_format_no_tmp_input_mentioned(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent")

        call_arg = mock_agent_instance.call_args[0][0]
        assert "INPUT FORMAT" not in call_arg


class TestAgentCreatorOutputFormat:
    def test_pdf_output_format_mentions_reportlab(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent", output_format="pdf")

        call_arg = mock_agent_instance.call_args[0][0]
        assert "reportlab" in call_arg

    def test_xlsx_output_format_mentions_openpyxl(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent", output_format="xlsx")

        call_arg = mock_agent_instance.call_args[0][0]
        assert "openpyxl" in call_arg

    def test_docx_output_format_mentions_python_docx(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent", output_format="docx")

        call_arg = mock_agent_instance.call_args[0][0]
        assert "python-docx" in call_arg

    def test_pptx_output_format_mentions_python_pptx(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent", output_format="pptx")

        call_arg = mock_agent_instance.call_args[0][0]
        assert "python-pptx" in call_arg

    def test_markdown_output_format_no_output_format_instruction(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent", output_format="markdown")

        call_arg = mock_agent_instance.call_args[0][0]
        # markdown is the default — no OUTPUT FORMAT instruction added
        assert "OUTPUT FORMAT" not in call_arg


# ── Default prompt injection ──────────────────────────────────────────────────


class TestAgentCreatorDefaultPrompt:
    def test_default_prompt_injected_in_context(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent", default_prompt="Run analysis")

        call_arg = mock_agent_instance.call_args[0][0]
        assert "Run analysis" in call_arg

    def test_no_default_prompt_no_prompt_instruction(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent")

        call_arg = mock_agent_instance.call_args[0][0]
        assert "DEFAULT PROMPT" not in call_arg


# ── Available secrets in context ──────────────────────────────────────────────


class TestAgentCreatorAvailableSecrets:
    def test_available_secrets_listed_in_context(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent", available_secrets=["my-key", "another-key"])

        call_arg = mock_agent_instance.call_args[0][0]
        assert "my-key" in call_arg
        assert "another-key" in call_arg

    def test_no_secrets_empty_list_no_explicit_secrets_note(self, mocker):
        """When available_secrets=[] and no platform-default model is matched,
        the secrets note should NOT appear in the context."""
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")
        # Use a non-platform-default model so "default" is not forced in
        mocker.patch("agents.agent_creator.PLATFORM_DEFAULT_MODELS", [])

        agent_creator_assistant(
            "Create agent",
            available_secrets=[],
            model_provider="anthropic",
            model_id="claude-custom-xyz",
        )

        call_arg = mock_agent_instance.call_args[0][0]
        assert "Available secrets" not in call_arg


# ── Model settings block in context ──────────────────────────────────────────


class TestAgentCreatorModelSettings:
    def test_model_provider_and_id_injected_when_specified(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant(
            "Create agent",
            model_provider="openai",
            model_id="gpt-4.1",
            temperature=0.5,
        )

        call_arg = mock_agent_instance.call_args[0][0]
        assert "openai" in call_arg
        assert "gpt-4.1" in call_arg
        assert "0.5" in call_arg

    def test_no_model_specified_no_model_settings_block(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent without model")

        call_arg = mock_agent_instance.call_args[0][0]
        # Without model_provider + model_id, the "Use exactly these model settings" block absent
        assert "Use exactly these model settings" not in call_arg


# ── Validation retry logic ────────────────────────────────────────────────────


class TestAgentCreatorValidationRetry:
    def test_retry_on_invalid_then_valid(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        validate_results = ["INVALID - some error", "VALID - ok"]
        validate_mock = mocker.patch(
            "agents.agent_creator.validate_yaml",
            side_effect=validate_results,
        )

        agent_creator_assistant("Create agent")

        # Agent should be called twice: initial + 1 fix attempt
        assert mock_agent_instance.call_count == 2
        # validate_yaml should be called at least twice
        assert validate_mock.call_count >= 2

    def test_max_retries_exhausted_returns_last_yaml(self, mocker):
        _make_mock_agent_cls(mocker, _VALID_YAML)
        # Always return INVALID — never succeeds
        mocker.patch(
            "agents.agent_creator.validate_yaml",
            return_value="INVALID - persistent error",
        )
        mock_agent_instance = mocker.MagicMock()
        mock_agent_instance.return_value = "last-yaml-str"
        mocker.patch("agents.agent_creator.Agent", return_value=mock_agent_instance)
        mocker.patch("agents.agent_creator.LiteLLMModel")

        result = agent_creator_assistant("Create agent")

        # agent should be called 1 (initial) + _MAX_VALIDATION_RETRIES times
        assert mock_agent_instance.call_count == 1 + _MAX_VALIDATION_RETRIES
        # result is whatever the agent last returned
        assert result == "last-yaml-str"

    def test_first_call_valid_agent_called_once(self, mocker):
        _mock_agent_cls, mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch("agents.agent_creator.validate_yaml", return_value="VALID - ok")

        agent_creator_assistant("Create agent")

        assert mock_agent_instance.call_count == 1


# ── Exception handling ────────────────────────────────────────────────────────


class TestAgentCreatorExceptionHandling:
    def test_runtime_error_returns_error_string(self, mocker):
        mocker.patch("agents.agent_creator.Agent", side_effect=RuntimeError("model down"))
        mocker.patch("agents.agent_creator.LiteLLMModel")

        result = agent_creator_assistant("Create agent")

        assert result.startswith("AGENT_CREATOR_ERROR:")
        assert "model down" in result

    def test_exception_message_format(self, mocker):
        mocker.patch("agents.agent_creator.Agent", side_effect=ValueError("bad config"))
        mocker.patch("agents.agent_creator.LiteLLMModel")

        result = agent_creator_assistant("Create agent")

        assert "AGENT_CREATOR_ERROR:" in result
        assert "bad config" in result

    def test_validate_yaml_exception_during_retry_still_returns(self, mocker):
        _mock_agent_cls, _mock_agent_instance = _make_mock_agent_cls(mocker, _VALID_YAML)
        mocker.patch(
            "agents.agent_creator.validate_yaml",
            side_effect=RuntimeError("validator crashed"),
        )

        result = agent_creator_assistant("Create agent")

        assert result.startswith("AGENT_CREATOR_ERROR:")
