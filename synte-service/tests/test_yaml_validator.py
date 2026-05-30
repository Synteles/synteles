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

"""Tests for tools/yaml_validator.py — validate_yaml pure function."""

from __future__ import annotations

from tools.yaml_validator import validate_yaml

# ── Minimal valid YAML fixture ───────────────────────────────────────────────

VALID_YAML = """\
agentlet:
  name: test-agent
  version: "1.0.0"
system_prompt: "You are a helpful assistant."
model:
  provider: azure_ai
  model_id: gpt-4o
prompt: "Do the task."
"""

VALID_YAML_WITH_FENCES = """\
```yaml
agentlet:
  name: test-agent
  version: "1.0.0"
system_prompt: "You are a helpful assistant."
model:
  provider: azure_ai
  model_id: gpt-4o
prompt: "Do the task."
```"""


class TestValidateYamlValid:
    def test_valid_yaml_starts_with_valid(self):
        result = validate_yaml(VALID_YAML)
        assert result.startswith("VALID")

    def test_valid_yaml_contains_confirmation_message(self):
        result = validate_yaml(VALID_YAML)
        assert "valid" in result.lower()

    def test_code_fences_stripped_and_still_valid(self):
        result = validate_yaml(VALID_YAML_WITH_FENCES)
        assert result.startswith("VALID")

    def test_code_fence_without_language_tag(self):
        content = "```\n" + VALID_YAML + "```"
        result = validate_yaml(content)
        assert result.startswith("VALID")

    def test_leading_trailing_whitespace_tolerated(self):
        result = validate_yaml("  \n" + VALID_YAML + "\n  ")
        assert result.startswith("VALID")


class TestValidateYamlSyntaxError:
    def test_invalid_yaml_syntax_starts_with_invalid(self):
        bad_yaml = "agentlet:\n  name: [\nbad: yaml: here"
        result = validate_yaml(bad_yaml)
        assert result.startswith("INVALID")

    def test_invalid_yaml_mentions_syntax_error(self):
        bad_yaml = "agentlet:\n  name: [\nbad: yaml: here"
        result = validate_yaml(bad_yaml)
        assert "syntax error" in result.lower()

    def test_tab_indentation_is_invalid_yaml(self):
        bad_yaml = "agentlet:\n\tname: test"
        result = validate_yaml(bad_yaml)
        assert result.startswith("INVALID")


class TestValidateYamlNotAMapping:
    def test_yaml_list_is_not_mapping(self):
        result = validate_yaml("- item1\n- item2\n")
        assert result.startswith("INVALID")
        assert "mapping" in result.lower()

    def test_yaml_scalar_is_not_mapping(self):
        result = validate_yaml("just a string\n")
        assert result.startswith("INVALID")
        assert "mapping" in result.lower()


class TestValidateYamlMissingRequiredFields:
    def test_missing_model_field(self):
        yaml_no_model = """\
agentlet:
  name: test-agent
system_prompt: "You are helpful."
"""
        result = validate_yaml(yaml_no_model)
        assert result.startswith("INVALID")

    def test_missing_system_prompt_field(self):
        yaml_no_prompt = """\
agentlet:
  name: test-agent
model:
  provider: azure_ai
  model_id: gpt-4o
"""
        result = validate_yaml(yaml_no_prompt)
        assert result.startswith("INVALID")

    def test_missing_agentlet_field(self):
        yaml_no_agentlet = """\
system_prompt: "You are helpful."
model:
  provider: azure_ai
  model_id: gpt-4o
"""
        result = validate_yaml(yaml_no_agentlet)
        assert result.startswith("INVALID")

    def test_error_count_in_message(self):
        # No model, no system_prompt, no agentlet — at least 3 errors
        result = validate_yaml("{}")
        assert result.startswith("INVALID")
        # The error message should list at least one numbered error
        assert "1." in result

    def test_model_missing_provider(self):
        yaml_no_provider = """\
agentlet:
  name: test-agent
system_prompt: "You are helpful."
model:
  model_id: gpt-4o
"""
        result = validate_yaml(yaml_no_provider)
        assert result.startswith("INVALID")

    def test_model_missing_model_id(self):
        yaml_no_model_id = """\
agentlet:
  name: test-agent
system_prompt: "You are helpful."
model:
  provider: azure_ai
"""
        result = validate_yaml(yaml_no_model_id)
        assert result.startswith("INVALID")


class TestValidateYamlMultipleErrors:
    def test_multiple_errors_each_listed(self):
        # Missing both model.provider and model.model_id  => 2 errors
        yaml_bad_model = """\
agentlet:
  name: test-agent
system_prompt: "You are helpful."
model: {}
"""
        result = validate_yaml(yaml_bad_model)
        assert result.startswith("INVALID")
        # At minimum error 1 must be listed
        assert "1." in result

    def test_path_info_present_in_error(self):
        yaml_bad_model = """\
agentlet:
  name: test-agent
system_prompt: "You are helpful."
model: {}
"""
        result = validate_yaml(yaml_bad_model)
        # The schema errors reference the 'model' path
        assert "model" in result or "provider" in result or "model_id" in result


class TestValidateYamlSchemaLoadFailure:
    def test_schema_load_failure_returns_invalid(self, mocker):
        mocker.patch(
            "tools.yaml_validator._load_schema",
            side_effect=OSError("file not found"),
        )
        result = validate_yaml(VALID_YAML)
        assert result.startswith("INVALID")
        assert "Could not load" in result
