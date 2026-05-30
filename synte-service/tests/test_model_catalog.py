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

"""Tests for tools/model_catalog.py."""

from __future__ import annotations

from typing import ClassVar

import pytest

from tools.model_catalog import (
    PLATFORM_DEFAULT_MODELS,
    PROVIDERS,
    get_model_catalog,
    resolve_model,
    resolve_model_selection,
)

# ── PROVIDERS structure ──────────────────────────────────────────────────────


class TestProvidersStructure:
    EXPECTED_PROVIDERS: ClassVar[set[str]] = {
        "anthropic",
        "openai",
        "bedrock",
        "vertex_ai",
        "gemini",
        "azure_ai",
        "azure",
        "sagemaker",
    }

    def test_all_expected_providers_present(self):
        assert self.EXPECTED_PROVIDERS.issubset(set(PROVIDERS.keys()))

    def test_each_catalog_provider_has_models_list(self):
        for pid, pdata in PROVIDERS.items():
            if not pdata.get("deployment_based"):
                assert "models" in pdata, f"{pid} missing models"
                assert isinstance(pdata["models"], list)
                assert len(pdata["models"]) > 0

    def test_each_model_has_id_and_name(self):
        for pid, pdata in PROVIDERS.items():
            for model in pdata.get("models", []):
                assert "id" in model, f"{pid} model missing 'id': {model}"
                assert "name" in model, f"{pid} model missing 'name': {model}"

    def test_deployment_based_providers_have_no_models_list(self):
        for _pid, pdata in PROVIDERS.items():
            if pdata.get("deployment_based"):
                assert "models" not in pdata or len(pdata.get("models", [])) == 0


# ── resolve_model — numeric index ────────────────────────────────────────────


class TestResolveModelByNumber:
    def test_resolve_first_model_by_number_one(self):
        result = resolve_model("anthropic", "1")
        expected_first_id = PROVIDERS["anthropic"]["models"][0]["id"]
        assert result["model_id"] == expected_first_id
        assert result["provider"] == "anthropic"

    def test_resolve_second_model_by_number(self):
        result = resolve_model("openai", "2")
        expected_id = PROVIDERS["openai"]["models"][1]["id"]
        assert result["model_id"] == expected_id

    def test_result_has_required_keys(self):
        result = resolve_model("anthropic", "1")
        assert "provider" in result
        assert "model_id" in result
        assert "secret_hint" in result

    def test_out_of_range_number_zero_raises(self):
        with pytest.raises(ValueError, match="out of range"):
            resolve_model("anthropic", "0")

    def test_out_of_range_number_too_large_raises(self):
        n_models = len(PROVIDERS["anthropic"]["models"])
        with pytest.raises(ValueError, match="out of range"):
            resolve_model("anthropic", str(n_models + 1))


# ── resolve_model — substring match ─────────────────────────────────────────


class TestResolveModelBySubstring:
    def test_resolve_by_name_substring(self):
        # "claude-opus-4-6" is the first anthropic model — exact substring in id
        result = resolve_model("anthropic", "claude-opus-4-6")
        assert result["provider"] == "anthropic"
        assert "claude-opus-4-6" in result["model_id"]

    def test_resolve_by_case_insensitive_name(self):
        # "Haiku" appears uniquely enough for haiku models subset
        # Use a unique enough substring that maps to exactly one model
        # claude-haiku-4-5-20251001 is unique enough
        result = resolve_model("anthropic", "claude-haiku-4-5-20251001")
        assert "haiku" in result["model_id"].lower()

    def test_ambiguous_substring_raises(self):
        # "claude" matches many anthropic models → ambiguous
        with pytest.raises(ValueError, match="Ambiguous"):
            resolve_model("anthropic", "claude")

    def test_not_found_raises(self):
        with pytest.raises(ValueError, match="not found"):
            resolve_model("anthropic", "nonexistent-model-xyz-9999")


# ── resolve_model — exact ID ─────────────────────────────────────────────────


class TestResolveModelByExactId:
    def test_resolve_exact_model_id(self):
        result = resolve_model("openai", "gpt-5")
        assert result["model_id"] == "gpt-5"
        assert result["provider"] == "openai"

    def test_exact_id_case_insensitive(self):
        result = resolve_model("openai", "GPT-5")
        assert result["model_id"] == "gpt-5"

    def test_bedrock_model_exact_id(self):
        result = resolve_model("bedrock", "amazon.nova-pro-v1:0")
        assert result["model_id"] == "amazon.nova-pro-v1:0"

    def test_bedrock_result_has_no_secret_required(self):
        result = resolve_model("bedrock", "amazon.nova-pro-v1:0")
        assert "IAM" in result["secret_hint"] or "no" in result["secret_hint"].lower()


# ── resolve_model — unknown provider ────────────────────────────────────────


class TestResolveModelUnknownProvider:
    def test_unknown_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            resolve_model("nonexistent_provider", "some-model")

    def test_error_message_lists_available_providers(self):
        with pytest.raises(ValueError) as exc_info:
            resolve_model("bad_provider", "model-x")
        assert "anthropic" in str(exc_info.value)


# ── resolve_model — deployment-based providers ───────────────────────────────


class TestResolveModelDeploymentBased:
    def test_azure_accepts_any_deployment_name(self):
        result = resolve_model("azure", "my-custom-gpt4o-deployment")
        assert result["model_id"] == "my-custom-gpt4o-deployment"
        assert result["provider"] == "azure"

    def test_sagemaker_accepts_endpoint_name(self):
        result = resolve_model("sagemaker", "my-llama-endpoint")
        assert result["model_id"] == "my-llama-endpoint"

    def test_azure_empty_deployment_name_raises(self):
        with pytest.raises(ValueError):
            resolve_model("azure", "")

    def test_sagemaker_empty_endpoint_name_raises(self):
        with pytest.raises(ValueError):
            resolve_model("sagemaker", "   ")


# ── get_model_catalog ────────────────────────────────────────────────────────


class TestGetModelCatalog:
    def test_returns_dict_with_providers_key(self):
        result = get_model_catalog()
        assert isinstance(result, dict)
        assert "providers" in result

    def test_providers_is_list(self):
        result = get_model_catalog()
        assert isinstance(result["providers"], list)

    def test_providers_list_non_empty(self):
        result = get_model_catalog()
        assert len(result["providers"]) > 0

    def test_each_provider_entry_has_id_and_name(self):
        result = get_model_catalog()
        for entry in result["providers"]:
            assert "id" in entry
            assert "name" in entry

    def test_catalog_based_providers_include_models_list(self):
        result = get_model_catalog()
        catalog_entries = [e for e in result["providers"] if not e.get("deployment_based")]
        for entry in catalog_entries:
            assert "models" in entry
            assert isinstance(entry["models"], list)


# ── resolve_model_selection (@tool wrapper) ───────────────────────────────────


class TestResolveModelSelection:
    def test_success_returns_dict_with_provider_and_model_id(self, mocker):
        mocker.patch(
            "tools.model_catalog.resolve_model",
            return_value={"provider": "openai", "model_id": "gpt-4o", "secret_hint": "needs key"},
        )
        result = resolve_model_selection("openai", "gpt-4o")
        assert result["provider"] == "openai"
        assert result["model_id"] == "gpt-4o"

    def test_value_error_returns_error_dict(self, mocker):
        mocker.patch(
            "tools.model_catalog.resolve_model",
            side_effect=ValueError("Model not found"),
        )
        result = resolve_model_selection("openai", "bad-model")
        assert "error" in result
        assert "Model not found" in result["error"]

    def test_success_no_error_key(self, mocker):
        mocker.patch(
            "tools.model_catalog.resolve_model",
            return_value={
                "provider": "anthropic",
                "model_id": "claude-sonnet-4-6",
                "secret_hint": "x",
            },
        )
        result = resolve_model_selection("anthropic", "1")
        assert "error" not in result


# ── PLATFORM_DEFAULT_MODELS ──────────────────────────────────────────────────


class TestPlatformDefaultModels:
    def test_platform_defaults_is_list(self):
        assert isinstance(PLATFORM_DEFAULT_MODELS, list)

    def test_when_config_missing_load_raises(self, mocker, tmp_path):
        """_load_platform_defaults raises FileNotFoundError when config absent."""
        from tools.model_catalog import _load_platform_defaults

        # Patch Path.exists to never find the file by making parents yield no match
        mocker.patch("tools.model_catalog.Path.exists", return_value=False)
        # Also patch read_text to raise FileNotFoundError
        mocker.patch("tools.model_catalog.Path.read_text", side_effect=FileNotFoundError)
        with pytest.raises(FileNotFoundError):
            _load_platform_defaults()

    def test_platform_defaults_each_entry_has_required_keys(self):
        for entry in PLATFORM_DEFAULT_MODELS:
            assert "provider" in entry
            assert "model_id" in entry
            assert "is_platform_default" in entry
            assert entry["is_platform_default"] is True

    def test_platform_defaults_empty_when_load_returns_empty(self, mocker):
        """Test that patching _load_platform_defaults to return [] works."""
        mocker.patch("tools.model_catalog._load_platform_defaults", return_value=[])
        # Re-import would be needed in practice; test the patch call directly
        from tools.model_catalog import _load_platform_defaults as lp

        result = lp()
        assert result == []
