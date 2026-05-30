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

"""
Static catalog of LLM providers and their available models for the Synteles Platform.

No API calls — always available. Exposes get_model_catalog and resolve_model_selection
as Strands @tool functions for use by the ChatAgent.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from strands import tool

PROVIDERS: dict[str, Any] = {
    "anthropic": {
        "name": "Anthropic",
        "description": "Direct Anthropic API — requires ANTHROPIC_API_KEY secret",
        "litellm_prefix": "anthropic/",
        "requires_secret": "ANTHROPIC_API_KEY",  # nosec B105
        "deployment_based": False,
        # Source: https://docs.anthropic.com/en/docs/about-claude/models/overview (2026-03-17)
        # Use snapshot IDs (with date suffix) for production — they are frozen and never change.
        # Alias IDs (without date suffix) always resolve to the latest snapshot of that line.
        "models": [
            # ── Current models ────────────────────────────────────────────────
            {"id": "claude-opus-4-6", "name": "Claude Opus 4.6 (alias — latest)"},
            {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6 (alias — latest)"},
            {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5"},
            {"id": "claude-haiku-4-5", "name": "Claude Haiku 4.5 (alias)"},
            # ── Legacy models (available, migration recommended) ──────────────
            {"id": "claude-sonnet-4-5-20250929", "name": "Claude Sonnet 4.5 (legacy)"},
            {"id": "claude-sonnet-4-5", "name": "Claude Sonnet 4.5 (alias, legacy)"},
            {"id": "claude-opus-4-5-20251101", "name": "Claude Opus 4.5 (legacy)"},
            {"id": "claude-opus-4-5", "name": "Claude Opus 4.5 (alias, legacy)"},
            {"id": "claude-opus-4-1-20250805", "name": "Claude Opus 4.1 (legacy)"},
            {"id": "claude-opus-4-1", "name": "Claude Opus 4.1 (alias, legacy)"},
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4 (legacy)"},
            {"id": "claude-sonnet-4-0", "name": "Claude Sonnet 4 (alias, legacy)"},
            {"id": "claude-opus-4-20250514", "name": "Claude Opus 4 (legacy)"},
            {"id": "claude-opus-4-0", "name": "Claude Opus 4 (alias, legacy)"},
            # ── Deprecated (retiring 2026-04-19) ─────────────────────────────
            {
                "id": "claude-3-haiku-20240307",
                "name": "Claude 3 Haiku (deprecated — use Haiku 4.5)",
            },
        ],
    },
    "openai": {
        "name": "OpenAI",
        "description": "Direct OpenAI API — requires OPENAI_API_KEY secret",
        "litellm_prefix": "openai/",
        "requires_secret": "OPENAI_API_KEY",  # nosec B105
        "deployment_based": False,
        # Source: https://platform.openai.com/docs/models (via OpenAI Python SDK, 2026-03-17)
        # Use dated snapshots (e.g. gpt-4.1-2025-04-14) for production stability.
        # Alias IDs (without date) always resolve to the latest snapshot of that line.
        "models": [
            # ── GPT-5 series (released Aug 2025) ─────────────────────────────
            {"id": "gpt-5", "name": "GPT-5 (latest flagship)", "family": "GPT-5"},
            {"id": "gpt-5-2025-08-07", "name": "GPT-5 (snapshot)", "family": "GPT-5"},
            {"id": "gpt-5-mini", "name": "GPT-5 Mini", "family": "GPT-5"},
            {"id": "gpt-5-mini-2025-08-07", "name": "GPT-5 Mini (snapshot)", "family": "GPT-5"},
            {"id": "gpt-5-nano", "name": "GPT-5 Nano", "family": "GPT-5"},
            {"id": "gpt-5-nano-2025-08-07", "name": "GPT-5 Nano (snapshot)", "family": "GPT-5"},
            # ── GPT-4.1 series (1M context, released Apr 2025) ───────────────
            {"id": "gpt-4.1", "name": "GPT-4.1 (recommended, 1M ctx)", "family": "GPT-4.1"},
            {"id": "gpt-4.1-2025-04-14", "name": "GPT-4.1 (snapshot)", "family": "GPT-4.1"},
            {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini (1M ctx)", "family": "GPT-4.1"},
            {
                "id": "gpt-4.1-mini-2025-04-14",
                "name": "GPT-4.1 Mini (snapshot)",
                "family": "GPT-4.1",
            },
            {"id": "gpt-4.1-nano", "name": "GPT-4.1 Nano (1M ctx)", "family": "GPT-4.1"},
            {
                "id": "gpt-4.1-nano-2025-04-14",
                "name": "GPT-4.1 Nano (snapshot)",
                "family": "GPT-4.1",
            },
            # ── o-series reasoning models ─────────────────────────────────────
            {"id": "o4-mini", "name": "o4-mini (efficient reasoning)", "family": "o-series"},
            {"id": "o4-mini-2025-04-16", "name": "o4-mini (snapshot)", "family": "o-series"},
            {"id": "o3", "name": "o3 (full reasoning)", "family": "o-series"},
            {"id": "o3-2025-04-16", "name": "o3 (snapshot)", "family": "o-series"},
            {"id": "o3-mini", "name": "o3-mini", "family": "o-series"},
            {"id": "o3-mini-2025-01-31", "name": "o3-mini (snapshot)", "family": "o-series"},
            {"id": "o1", "name": "o1", "family": "o-series"},
            {"id": "o1-2024-12-17", "name": "o1 (snapshot)", "family": "o-series"},
            {"id": "o1-mini", "name": "o1-mini", "family": "o-series"},
            {"id": "o1-mini-2024-09-12", "name": "o1-mini (snapshot)", "family": "o-series"},
            # ── GPT-4o series (128K context) ─────────────────────────────────
            {"id": "gpt-4o", "name": "GPT-4o", "family": "GPT-4o"},
            {"id": "gpt-4o-2024-11-20", "name": "GPT-4o (snapshot)", "family": "GPT-4o"},
            {"id": "gpt-4o-2024-08-06", "name": "GPT-4o Aug 2024", "family": "GPT-4o"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "family": "GPT-4o"},
            {"id": "gpt-4o-mini-2024-07-18", "name": "GPT-4o Mini (snapshot)", "family": "GPT-4o"},
            # ── GPT-4 Turbo (legacy) ──────────────────────────────────────────
            {
                "id": "gpt-4-turbo",
                "name": "GPT-4 Turbo (legacy, 128K ctx)",
                "family": "GPT-4 Legacy",
            },
            {
                "id": "gpt-4-turbo-2024-04-09",
                "name": "GPT-4 Turbo (snapshot, legacy)",
                "family": "GPT-4 Legacy",
            },
            # ── GPT-3.5 Turbo (legacy) ────────────────────────────────────────
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo (legacy)", "family": "GPT-3.5 Legacy"},
            {
                "id": "gpt-3.5-turbo-0125",
                "name": "GPT-3.5 Turbo (snapshot, legacy)",
                "family": "GPT-3.5 Legacy",
            },
        ],
    },
    "bedrock": {
        "name": "AWS Bedrock",
        "description": "AWS-managed access — requires AWS IAM permissions, no API key secret needed",
        "litellm_prefix": "bedrock/",
        "requires_secret": None,  # nosec B105
        "deployment_based": False,
        # Sources:
        #   https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html
        #   https://docs.aws.amazon.com/bedrock/latest/userguide/inference-profiles-support.html
        #   (retrieved 2026-03-17)
        # Text/chat models only — image generation, embeddings, rerank, audio, and video
        # models are excluded. Use base model IDs for single-region; cross-region inference
        # profile IDs (e.g. us.*, eu.*, global.*) for multi-region HA.
        "models": [
            # ── Anthropic Claude (base) ───────────────────────────────────────
            {
                "id": "anthropic.claude-sonnet-4-6",
                "name": "Claude Sonnet 4.6",
                "family": "Anthropic",
            },
            {
                "id": "anthropic.claude-opus-4-6-v1",
                "name": "Claude Opus 4.6",
                "family": "Anthropic",
            },
            {
                "id": "anthropic.claude-sonnet-4-5-20250929-v1:0",
                "name": "Claude Sonnet 4.5",
                "family": "Anthropic",
            },
            {
                "id": "anthropic.claude-opus-4-5-20251101-v1:0",
                "name": "Claude Opus 4.5",
                "family": "Anthropic",
            },
            {
                "id": "anthropic.claude-sonnet-4-20250514-v1:0",
                "name": "Claude Sonnet 4",
                "family": "Anthropic",
            },
            {
                "id": "anthropic.claude-opus-4-1-20250805-v1:0",
                "name": "Claude Opus 4.1",
                "family": "Anthropic",
            },
            {
                "id": "anthropic.claude-opus-4-20250514-v1:0",
                "name": "Claude Opus 4",
                "family": "Anthropic",
            },
            {
                "id": "anthropic.claude-haiku-4-5-20251001-v1:0",
                "name": "Claude Haiku 4.5",
                "family": "Anthropic",
            },
            {
                "id": "anthropic.claude-3-5-haiku-20241022-v1:0",
                "name": "Claude 3.5 Haiku",
                "family": "Anthropic",
            },
            {
                "id": "anthropic.claude-3-haiku-20240307-v1:0",
                "name": "Claude 3 Haiku",
                "family": "Anthropic",
            },
            # ── Amazon Nova (text, base) ──────────────────────────────────────
            {"id": "amazon.nova-premier-v1:0", "name": "Nova Premier", "family": "Amazon Nova"},
            {"id": "amazon.nova-pro-v1:0", "name": "Nova Pro", "family": "Amazon Nova"},
            {"id": "amazon.nova-lite-v1:0", "name": "Nova Lite", "family": "Amazon Nova"},
            {"id": "amazon.nova-micro-v1:0", "name": "Nova Micro", "family": "Amazon Nova"},
            {"id": "amazon.nova-2-lite-v1:0", "name": "Nova 2 Lite", "family": "Amazon Nova"},
            # ── Meta Llama (base) ─────────────────────────────────────────────
            {
                "id": "meta.llama4-maverick-17b-instruct-v1:0",
                "name": "Llama 4 Maverick 17B",
                "family": "Meta Llama",
            },
            {
                "id": "meta.llama4-scout-17b-instruct-v1:0",
                "name": "Llama 4 Scout 17B",
                "family": "Meta Llama",
            },
            {
                "id": "meta.llama3-3-70b-instruct-v1:0",
                "name": "Llama 3.3 70B",
                "family": "Meta Llama",
            },
            {
                "id": "meta.llama3-2-90b-instruct-v1:0",
                "name": "Llama 3.2 90B",
                "family": "Meta Llama",
            },
            {
                "id": "meta.llama3-2-11b-instruct-v1:0",
                "name": "Llama 3.2 11B",
                "family": "Meta Llama",
            },
            {
                "id": "meta.llama3-2-3b-instruct-v1:0",
                "name": "Llama 3.2 3B",
                "family": "Meta Llama",
            },
            {
                "id": "meta.llama3-2-1b-instruct-v1:0",
                "name": "Llama 3.2 1B",
                "family": "Meta Llama",
            },
            {
                "id": "meta.llama3-1-405b-instruct-v1:0",
                "name": "Llama 3.1 405B",
                "family": "Meta Llama",
            },
            {
                "id": "meta.llama3-1-70b-instruct-v1:0",
                "name": "Llama 3.1 70B",
                "family": "Meta Llama",
            },
            {
                "id": "meta.llama3-1-8b-instruct-v1:0",
                "name": "Llama 3.1 8B",
                "family": "Meta Llama",
            },
            {"id": "meta.llama3-70b-instruct-v1:0", "name": "Llama 3 70B", "family": "Meta Llama"},
            {"id": "meta.llama3-8b-instruct-v1:0", "name": "Llama 3 8B", "family": "Meta Llama"},
            # ── Mistral (base) ────────────────────────────────────────────────
            {
                "id": "mistral.mistral-large-3-675b-instruct",
                "name": "Mistral Large 3",
                "family": "Mistral",
            },
            {
                "id": "mistral.pixtral-large-2502-v1:0",
                "name": "Pixtral Large 25.02",
                "family": "Mistral",
            },
            {
                "id": "mistral.magistral-small-2509",
                "name": "Magistral Small 25.09",
                "family": "Mistral",
            },
            {
                "id": "mistral.devstral-2-123b",
                "name": "Devstral 2 123B (code)",
                "family": "Mistral",
            },
            {
                "id": "mistral.mistral-large-2407-v1:0",
                "name": "Mistral Large 24.07",
                "family": "Mistral",
            },
            {
                "id": "mistral.ministral-3-14b-instruct",
                "name": "Ministral 14B",
                "family": "Mistral",
            },
            {"id": "mistral.ministral-3-8b-instruct", "name": "Ministral 8B", "family": "Mistral"},
            {"id": "mistral.ministral-3-3b-instruct", "name": "Ministral 3B", "family": "Mistral"},
            {
                "id": "mistral.mixtral-8x7b-instruct-v0:1",
                "name": "Mixtral 8x7B",
                "family": "Mistral",
            },
            {"id": "mistral.mistral-7b-instruct-v0:2", "name": "Mistral 7B", "family": "Mistral"},
            # ── DeepSeek (base) ───────────────────────────────────────────────
            {"id": "deepseek.v3.2", "name": "DeepSeek V3.2", "family": "DeepSeek"},
            {"id": "deepseek.v3-v1:0", "name": "DeepSeek V3.1", "family": "DeepSeek"},
            {"id": "deepseek.r1-v1:0", "name": "DeepSeek R1 (reasoning)", "family": "DeepSeek"},
            # ── Google Gemma (base) ───────────────────────────────────────────
            {"id": "google.gemma-3-27b-it", "name": "Gemma 3 27B", "family": "Google Gemma"},
            {"id": "google.gemma-3-12b-it", "name": "Gemma 3 12B", "family": "Google Gemma"},
            {"id": "google.gemma-3-4b-it", "name": "Gemma 3 4B", "family": "Google Gemma"},
            # ── Qwen (base) ───────────────────────────────────────────────────
            {
                "id": "qwen.qwen3-coder-480b-a35b-v1:0",
                "name": "Qwen3 Coder 480B (code)",
                "family": "Qwen",
            },
            {"id": "qwen.qwen3-235b-a22b-2507-v1:0", "name": "Qwen3 235B", "family": "Qwen"},
            {
                "id": "qwen.qwen3-coder-30b-a3b-v1:0",
                "name": "Qwen3 Coder 30B (code)",
                "family": "Qwen",
            },
            {"id": "qwen.qwen3-32b-v1:0", "name": "Qwen3 32B", "family": "Qwen"},
            # ── Cohere Command (base) ─────────────────────────────────────────
            {"id": "cohere.command-r-plus-v1:0", "name": "Command R+", "family": "Cohere"},
            {"id": "cohere.command-r-v1:0", "name": "Command R", "family": "Cohere"},
            # ── AI21 Jamba (base) ─────────────────────────────────────────────
            {"id": "ai21.jamba-1-5-large-v1:0", "name": "Jamba 1.5 Large", "family": "AI21"},
            {"id": "ai21.jamba-1-5-mini-v1:0", "name": "Jamba 1.5 Mini", "family": "AI21"},
            # ── MiniMax (base) ────────────────────────────────────────────────
            {"id": "minimax.minimax-m2.1", "name": "MiniMax M2.1", "family": "MiniMax"},
            {"id": "minimax.minimax-m2", "name": "MiniMax M2", "family": "MiniMax"},
            # ── Moonshot Kimi (base) ──────────────────────────────────────────
            {"id": "moonshotai.kimi-k2.5", "name": "Kimi K2.5", "family": "Moonshot"},
            {"id": "moonshot.kimi-k2-thinking", "name": "Kimi K2 Thinking", "family": "Moonshot"},
            # ── NVIDIA Nemotron (base) ────────────────────────────────────────
            {"id": "nvidia.nemotron-nano-3-30b", "name": "Nemotron Nano 30B", "family": "NVIDIA"},
            {"id": "nvidia.nemotron-nano-12b-v2", "name": "Nemotron Nano 12B", "family": "NVIDIA"},
            {"id": "nvidia.nemotron-nano-9b-v2", "name": "Nemotron Nano 9B", "family": "NVIDIA"},
            # ── Writer Palmyra (base) ─────────────────────────────────────────
            {"id": "writer.palmyra-x5-v1:0", "name": "Palmyra X5", "family": "Writer"},
            {"id": "writer.palmyra-x4-v1:0", "name": "Palmyra X4", "family": "Writer"},
            # ── Z.AI GLM (base) ───────────────────────────────────────────────
            {"id": "zai.glm-4.7", "name": "GLM 4.7", "family": "Z.AI"},
            {"id": "zai.glm-4.7-flash", "name": "GLM 4.7 Flash", "family": "Z.AI"},
            # ════════════════════════════════════════════════════════════════════
            # Cross-Region Inference Profiles
            # Use these for multi-region HA. They route across multiple AWS regions
            # automatically. Profile ID = <geo-prefix>.<base-model-id>
            # ════════════════════════════════════════════════════════════════════
            # ── global.* — all commercial regions ────────────────────────────
            {
                "id": "global.anthropic.claude-opus-4-6-v1",
                "name": "Claude Opus 4.6 [global]",
                "family": "Anthropic (global)",
            },
            {
                "id": "global.anthropic.claude-opus-4-5-20251101-v1:0",
                "name": "Claude Opus 4.5 [global]",
                "family": "Anthropic (global)",
            },
            {
                "id": "global.anthropic.claude-sonnet-4-6",
                "name": "Claude Sonnet 4.6 [global]",
                "family": "Anthropic (global)",
            },
            {
                "id": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "name": "Claude Sonnet 4.5 [global]",
                "family": "Anthropic (global)",
            },
            {
                "id": "global.anthropic.claude-sonnet-4-20250514-v1:0",
                "name": "Claude Sonnet 4 [global]",
                "family": "Anthropic (global)",
            },
            {
                "id": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
                "name": "Claude Haiku 4.5 [global]",
                "family": "Anthropic (global)",
            },
            {
                "id": "global.amazon.nova-2-lite-v1:0",
                "name": "Nova 2 Lite [global]",
                "family": "Amazon Nova (global)",
            },
            # ── us.* — US regions ────────────────────────────────────────────
            {
                "id": "us.anthropic.claude-opus-4-6-v1",
                "name": "Claude Opus 4.6 [us]",
                "family": "Anthropic (us)",
            },
            {
                "id": "us.anthropic.claude-opus-4-5-20251101-v1:0",
                "name": "Claude Opus 4.5 [us]",
                "family": "Anthropic (us)",
            },
            {
                "id": "us.anthropic.claude-opus-4-20250514-v1:0",
                "name": "Claude Opus 4 [us]",
                "family": "Anthropic (us)",
            },
            {
                "id": "us.anthropic.claude-opus-4-1-20250805-v1:0",
                "name": "Claude Opus 4.1 [us]",
                "family": "Anthropic (us)",
            },
            {
                "id": "us.anthropic.claude-sonnet-4-6",
                "name": "Claude Sonnet 4.6 [us]",
                "family": "Anthropic (us)",
            },
            {
                "id": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "name": "Claude Sonnet 4.5 [us]",
                "family": "Anthropic (us)",
            },
            {
                "id": "us.anthropic.claude-sonnet-4-20250514-v1:0",
                "name": "Claude Sonnet 4 [us]",
                "family": "Anthropic (us)",
            },
            {
                "id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
                "name": "Claude Haiku 4.5 [us]",
                "family": "Anthropic (us)",
            },
            {
                "id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                "name": "Claude 3.7 Sonnet [us]",
                "family": "Anthropic (us)",
            },
            {
                "id": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "name": "Claude 3.5 Sonnet v2 [us]",
                "family": "Anthropic (us)",
            },
            {
                "id": "us.anthropic.claude-3-5-sonnet-20240620-v1:0",
                "name": "Claude 3.5 Sonnet [us]",
                "family": "Anthropic (us)",
            },
            {
                "id": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
                "name": "Claude 3.5 Haiku [us]",
                "family": "Anthropic (us)",
            },
            {
                "id": "us.anthropic.claude-3-opus-20240229-v1:0",
                "name": "Claude 3 Opus [us]",
                "family": "Anthropic (us)",
            },
            {
                "id": "us.anthropic.claude-3-haiku-20240307-v1:0",
                "name": "Claude 3 Haiku [us]",
                "family": "Anthropic (us)",
            },
            {
                "id": "us.amazon.nova-premier-v1:0",
                "name": "Nova Premier [us]",
                "family": "Amazon Nova (us)",
            },
            {
                "id": "us.amazon.nova-pro-v1:0",
                "name": "Nova Pro [us]",
                "family": "Amazon Nova (us)",
            },
            {
                "id": "us.amazon.nova-lite-v1:0",
                "name": "Nova Lite [us]",
                "family": "Amazon Nova (us)",
            },
            {
                "id": "us.amazon.nova-micro-v1:0",
                "name": "Nova Micro [us]",
                "family": "Amazon Nova (us)",
            },
            {
                "id": "us.amazon.nova-2-lite-v1:0",
                "name": "Nova 2 Lite [us]",
                "family": "Amazon Nova (us)",
            },
            {
                "id": "us.meta.llama4-maverick-17b-instruct-v1:0",
                "name": "Llama 4 Maverick 17B [us]",
                "family": "Meta Llama (us)",
            },
            {
                "id": "us.meta.llama4-scout-17b-instruct-v1:0",
                "name": "Llama 4 Scout 17B [us]",
                "family": "Meta Llama (us)",
            },
            {
                "id": "us.meta.llama3-3-70b-instruct-v1:0",
                "name": "Llama 3.3 70B [us]",
                "family": "Meta Llama (us)",
            },
            {
                "id": "us.meta.llama3-2-90b-instruct-v1:0",
                "name": "Llama 3.2 90B [us]",
                "family": "Meta Llama (us)",
            },
            {
                "id": "us.meta.llama3-2-11b-instruct-v1:0",
                "name": "Llama 3.2 11B [us]",
                "family": "Meta Llama (us)",
            },
            {
                "id": "us.meta.llama3-2-3b-instruct-v1:0",
                "name": "Llama 3.2 3B [us]",
                "family": "Meta Llama (us)",
            },
            {
                "id": "us.meta.llama3-2-1b-instruct-v1:0",
                "name": "Llama 3.2 1B [us]",
                "family": "Meta Llama (us)",
            },
            {
                "id": "us.meta.llama3-1-405b-instruct-v1:0",
                "name": "Llama 3.1 405B [us]",
                "family": "Meta Llama (us)",
            },
            {
                "id": "us.meta.llama3-1-70b-instruct-v1:0",
                "name": "Llama 3.1 70B [us]",
                "family": "Meta Llama (us)",
            },
            {
                "id": "us.meta.llama3-1-8b-instruct-v1:0",
                "name": "Llama 3.1 8B [us]",
                "family": "Meta Llama (us)",
            },
            {"id": "us.deepseek.r1-v1:0", "name": "DeepSeek R1 [us]", "family": "DeepSeek (us)"},
            {
                "id": "us.mistral.pixtral-large-2502-v1:0",
                "name": "Pixtral Large 25.02 [us]",
                "family": "Mistral (us)",
            },
            {"id": "us.writer.palmyra-x5-v1:0", "name": "Palmyra X5 [us]", "family": "Writer (us)"},
            {"id": "us.writer.palmyra-x4-v1:0", "name": "Palmyra X4 [us]", "family": "Writer (us)"},
            # ── eu.* — European regions ──────────────────────────────────────
            {
                "id": "eu.anthropic.claude-opus-4-6-v1",
                "name": "Claude Opus 4.6 [eu]",
                "family": "Anthropic (eu)",
            },
            {
                "id": "eu.anthropic.claude-opus-4-5-20251101-v1:0",
                "name": "Claude Opus 4.5 [eu]",
                "family": "Anthropic (eu)",
            },
            {
                "id": "eu.anthropic.claude-sonnet-4-6",
                "name": "Claude Sonnet 4.6 [eu]",
                "family": "Anthropic (eu)",
            },
            {
                "id": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "name": "Claude Sonnet 4.5 [eu]",
                "family": "Anthropic (eu)",
            },
            {
                "id": "eu.anthropic.claude-sonnet-4-20250514-v1:0",
                "name": "Claude Sonnet 4 [eu]",
                "family": "Anthropic (eu)",
            },
            {
                "id": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
                "name": "Claude Haiku 4.5 [eu]",
                "family": "Anthropic (eu)",
            },
            {
                "id": "eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
                "name": "Claude 3.7 Sonnet [eu]",
                "family": "Anthropic (eu)",
            },
            {
                "id": "eu.anthropic.claude-3-5-sonnet-20240620-v1:0",
                "name": "Claude 3.5 Sonnet [eu]",
                "family": "Anthropic (eu)",
            },
            {
                "id": "eu.anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet [eu]",
                "family": "Anthropic (eu)",
            },
            {
                "id": "eu.anthropic.claude-3-haiku-20240307-v1:0",
                "name": "Claude 3 Haiku [eu]",
                "family": "Anthropic (eu)",
            },
            {
                "id": "eu.amazon.nova-pro-v1:0",
                "name": "Nova Pro [eu]",
                "family": "Amazon Nova (eu)",
            },
            {
                "id": "eu.amazon.nova-lite-v1:0",
                "name": "Nova Lite [eu]",
                "family": "Amazon Nova (eu)",
            },
            {
                "id": "eu.amazon.nova-micro-v1:0",
                "name": "Nova Micro [eu]",
                "family": "Amazon Nova (eu)",
            },
            {
                "id": "eu.amazon.nova-2-lite-v1:0",
                "name": "Nova 2 Lite [eu]",
                "family": "Amazon Nova (eu)",
            },
            {
                "id": "eu.meta.llama3-2-3b-instruct-v1:0",
                "name": "Llama 3.2 3B [eu]",
                "family": "Meta Llama (eu)",
            },
            {
                "id": "eu.meta.llama3-2-1b-instruct-v1:0",
                "name": "Llama 3.2 1B [eu]",
                "family": "Meta Llama (eu)",
            },
            {
                "id": "eu.mistral.pixtral-large-2502-v1:0",
                "name": "Pixtral Large 25.02 [eu]",
                "family": "Mistral (eu)",
            },
            # ── apac.* — Asia-Pacific regions ────────────────────────────────
            {
                "id": "apac.anthropic.claude-sonnet-4-20250514-v1:0",
                "name": "Claude Sonnet 4 [apac]",
                "family": "Anthropic (apac)",
            },
            {
                "id": "apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
                "name": "Claude 3.7 Sonnet [apac]",
                "family": "Anthropic (apac)",
            },
            {
                "id": "apac.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "name": "Claude 3.5 Sonnet v2 [apac]",
                "family": "Anthropic (apac)",
            },
            {
                "id": "apac.anthropic.claude-3-5-sonnet-20240620-v1:0",
                "name": "Claude 3.5 Sonnet [apac]",
                "family": "Anthropic (apac)",
            },
            {
                "id": "apac.anthropic.claude-3-sonnet-20240229-v1:0",
                "name": "Claude 3 Sonnet [apac]",
                "family": "Anthropic (apac)",
            },
            {
                "id": "apac.anthropic.claude-3-haiku-20240307-v1:0",
                "name": "Claude 3 Haiku [apac]",
                "family": "Anthropic (apac)",
            },
            {
                "id": "apac.amazon.nova-pro-v1:0",
                "name": "Nova Pro [apac]",
                "family": "Amazon Nova (apac)",
            },
            {
                "id": "apac.amazon.nova-lite-v1:0",
                "name": "Nova Lite [apac]",
                "family": "Amazon Nova (apac)",
            },
            {
                "id": "apac.amazon.nova-micro-v1:0",
                "name": "Nova Micro [apac]",
                "family": "Amazon Nova (apac)",
            },
            # ── au.* — Australia ──────────────────────────────────────────────
            {
                "id": "au.anthropic.claude-opus-4-6-v1",
                "name": "Claude Opus 4.6 [au]",
                "family": "Anthropic (au)",
            },
            {
                "id": "au.anthropic.claude-sonnet-4-6",
                "name": "Claude Sonnet 4.6 [au]",
                "family": "Anthropic (au)",
            },
            {
                "id": "au.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "name": "Claude Sonnet 4.5 [au]",
                "family": "Anthropic (au)",
            },
            {
                "id": "au.anthropic.claude-haiku-4-5-20251001-v1:0",
                "name": "Claude Haiku 4.5 [au]",
                "family": "Anthropic (au)",
            },
            # ── jp.* — Japan ──────────────────────────────────────────────────
            {
                "id": "jp.anthropic.claude-sonnet-4-6",
                "name": "Claude Sonnet 4.6 [jp]",
                "family": "Anthropic (jp)",
            },
            {
                "id": "jp.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "name": "Claude Sonnet 4.5 [jp]",
                "family": "Anthropic (jp)",
            },
            {
                "id": "jp.anthropic.claude-haiku-4-5-20251001-v1:0",
                "name": "Claude Haiku 4.5 [jp]",
                "family": "Anthropic (jp)",
            },
            {
                "id": "jp.amazon.nova-2-lite-v1:0",
                "name": "Nova 2 Lite [jp]",
                "family": "Amazon Nova (jp)",
            },
        ],
        "cross_region_profiles": {
            "global": "All commercial AWS regions (newest models only)",
            "us": "US regions (broadest model selection)",
            "eu": "European regions (GDPR-friendly, includes eu-central-1)",
            "apac": "Asia-Pacific regions",
            "au": "Australia (Claude 4.x only)",
            "jp": "Japan (Claude 4.x + Nova 2 Lite)",
        },
    },
    "vertex_ai": {
        "name": "Google Vertex AI",
        "description": "GCP-managed — requires GCP credentials secret",
        "litellm_prefix": "vertex_ai/",
        "requires_secret": "GCP credentials",  # nosec B105
        "deployment_based": False,
        # Source: https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models (2026-03-17)
        # Alias IDs (no version suffix) auto-update to the latest stable release.
        # Pinned version IDs (e.g. -001) are frozen with explicit retirement dates.
        # Note: Gemini 1.5 series retired on Vertex AI (Sep 24, 2025) — not included.
        "models": [
            # ── Gemini 2.5 series (GA) ────────────────────────────────────────
            {
                "id": "gemini-2.5-pro",
                "name": "Gemini 2.5 Pro (recommended, 1M ctx)",
                "family": "Gemini 2.5",
            },
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash (1M ctx)", "family": "Gemini 2.5"},
            {
                "id": "gemini-2.5-flash-lite",
                "name": "Gemini 2.5 Flash-Lite (1M ctx)",
                "family": "Gemini 2.5",
            },
            # ── Gemini 2.0 series (GA) ────────────────────────────────────────
            {
                "id": "gemini-2.0-flash",
                "name": "Gemini 2.0 Flash (alias, 1M ctx)",
                "family": "Gemini 2.0",
            },
            {
                "id": "gemini-2.0-flash-001",
                "name": "Gemini 2.0 Flash 001 (pinned)",
                "family": "Gemini 2.0",
            },
            {
                "id": "gemini-2.0-flash-lite",
                "name": "Gemini 2.0 Flash-Lite (alias, 1M ctx)",
                "family": "Gemini 2.0",
            },
            {
                "id": "gemini-2.0-flash-lite-001",
                "name": "Gemini 2.0 Flash-Lite 001 (pinned)",
                "family": "Gemini 2.0",
            },
        ],
    },
    "gemini": {
        "name": "Google AI Studio",
        "description": "Direct Gemini API — requires GEMINI_API_KEY secret",
        "litellm_prefix": "gemini/",
        "requires_secret": "GEMINI_API_KEY",  # nosec B105
        "deployment_based": False,
        # Source: https://ai.google.dev/gemini-api/docs/models (2026-03-17)
        # Alias IDs (no version suffix) auto-update; versioned IDs are frozen.
        "models": [
            # ── Gemini 2.5 series (GA / Preview) ─────────────────────────────
            {
                "id": "gemini-2.5-pro",
                "name": "Gemini 2.5 Pro (recommended, 1M ctx)",
                "family": "Gemini 2.5",
            },
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash (1M ctx)", "family": "Gemini 2.5"},
            {
                "id": "gemini-2.5-flash-lite",
                "name": "Gemini 2.5 Flash-Lite (1M ctx)",
                "family": "Gemini 2.5",
            },
            {
                "id": "gemini-2.5-pro-preview-05-06",
                "name": "Gemini 2.5 Pro Preview (pinned)",
                "family": "Gemini 2.5",
            },
            {
                "id": "gemini-2.5-flash-preview-05-20",
                "name": "Gemini 2.5 Flash Preview (pinned)",
                "family": "Gemini 2.5",
            },
            # ── Gemini 2.0 series (GA) ────────────────────────────────────────
            {
                "id": "gemini-2.0-flash",
                "name": "Gemini 2.0 Flash (alias, 1M ctx)",
                "family": "Gemini 2.0",
            },
            {
                "id": "gemini-2.0-flash-001",
                "name": "Gemini 2.0 Flash 001 (pinned)",
                "family": "Gemini 2.0",
            },
            {
                "id": "gemini-2.0-flash-lite",
                "name": "Gemini 2.0 Flash-Lite (alias, 1M ctx)",
                "family": "Gemini 2.0",
            },
            {
                "id": "gemini-2.0-flash-lite-001",
                "name": "Gemini 2.0 Flash-Lite 001 (pinned)",
                "family": "Gemini 2.0",
            },
            {
                "id": "gemini-2.0-pro-exp",
                "name": "Gemini 2.0 Pro Experimental (2M ctx)",
                "family": "Gemini 2.0",
            },
            {
                "id": "gemini-2.0-flash-thinking-exp-01-21",
                "name": "Gemini 2.0 Flash Thinking Exp",
                "family": "Gemini 2.0",
            },
            # ── Gemini 1.5 series (legacy — may still be accessible via Gemini API) ──
            {
                "id": "gemini-1.5-pro",
                "name": "Gemini 1.5 Pro (legacy, 2M ctx)",
                "family": "Gemini 1.5 Legacy",
            },
            {
                "id": "gemini-1.5-pro-latest",
                "name": "Gemini 1.5 Pro Latest (legacy alias)",
                "family": "Gemini 1.5 Legacy",
            },
            {
                "id": "gemini-1.5-pro-002",
                "name": "Gemini 1.5 Pro 002 (legacy, pinned)",
                "family": "Gemini 1.5 Legacy",
            },
            {
                "id": "gemini-1.5-flash",
                "name": "Gemini 1.5 Flash (legacy, 1M ctx)",
                "family": "Gemini 1.5 Legacy",
            },
            {
                "id": "gemini-1.5-flash-latest",
                "name": "Gemini 1.5 Flash Latest (legacy alias)",
                "family": "Gemini 1.5 Legacy",
            },
            {
                "id": "gemini-1.5-flash-002",
                "name": "Gemini 1.5 Flash 002 (legacy, pinned)",
                "family": "Gemini 1.5 Legacy",
            },
            {
                "id": "gemini-1.5-flash-8b",
                "name": "Gemini 1.5 Flash-8B (legacy)",
                "family": "Gemini 1.5 Legacy",
            },
        ],
    },
    "azure_ai": {
        "name": "Azure AI",
        "description": "Azure AI Foundry — requires AZURE_AI_API_KEY + AZURE_AI_API_BASE secrets",
        "litellm_prefix": "azure_ai/",
        "requires_secret": "AZURE_AI_API_KEY",  # nosec B105
        "deployment_based": False,
        # Source: https://learn.microsoft.com/en-us/azure/ai-foundry/model-inference/concepts/models (2026-03-17)
        # Model IDs are the serverless deployment names used in the Azure AI inference API.
        "models": [
            # ── Azure OpenAI (GPT / o-series) ─────────────────────────────────
            {"id": "gpt-4.1", "name": "GPT-4.1 (recommended, 1M ctx)", "family": "Azure OpenAI"},
            {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini (1M ctx)", "family": "Azure OpenAI"},
            {"id": "gpt-4.1-nano", "name": "GPT-4.1 Nano (1M ctx)", "family": "Azure OpenAI"},
            {"id": "gpt-4o", "name": "GPT-4o", "family": "Azure OpenAI"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "family": "Azure OpenAI"},
            {"id": "o4-mini", "name": "o4-mini (reasoning)", "family": "Azure OpenAI"},
            {"id": "o3", "name": "o3 (reasoning)", "family": "Azure OpenAI"},
            {"id": "o3-mini", "name": "o3-mini (reasoning)", "family": "Azure OpenAI"},
            {"id": "o1", "name": "o1 (reasoning)", "family": "Azure OpenAI"},
            {"id": "o1-mini", "name": "o1-mini (reasoning)", "family": "Azure OpenAI"},
            # ── Anthropic Claude (via Azure Marketplace) ─────────────────────
            {"id": "claude-opus-4-6", "name": "Claude Opus 4.6", "family": "Anthropic"},
            {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "family": "Anthropic"},
            {"id": "claude-opus-4-5", "name": "Claude Opus 4.5", "family": "Anthropic"},
            {"id": "claude-sonnet-4-5", "name": "Claude Sonnet 4.5", "family": "Anthropic"},
            {"id": "claude-opus-4-1", "name": "Claude Opus 4.1", "family": "Anthropic"},
            {"id": "claude-haiku-4-5", "name": "Claude Haiku 4.5", "family": "Anthropic"},
            # ── Meta Llama ────────────────────────────────────────────────────
            {
                "id": "Llama-4-Maverick-17B-128E-Instruct-FP8",
                "name": "Llama 4 Maverick 17B (FP8)",
                "family": "Meta Llama",
            },
            {
                "id": "Llama-4-Scout-17B-16E-Instruct",
                "name": "Llama 4 Scout 17B",
                "family": "Meta Llama",
            },
            {"id": "Llama-3.3-70B-Instruct", "name": "Llama 3.3 70B", "family": "Meta Llama"},
            {
                "id": "Meta-Llama-3.1-405B-Instruct",
                "name": "Llama 3.1 405B",
                "family": "Meta Llama",
            },
            {"id": "Meta-Llama-3.1-8B-Instruct", "name": "Llama 3.1 8B", "family": "Meta Llama"},
            {
                "id": "Llama-3.2-90B-Vision-Instruct",
                "name": "Llama 3.2 90B Vision",
                "family": "Meta Llama",
            },
            {
                "id": "Llama-3.2-11B-Vision-Instruct",
                "name": "Llama 3.2 11B Vision",
                "family": "Meta Llama",
            },
            {"id": "Llama-3.2-3B-Instruct", "name": "Llama 3.2 3B", "family": "Meta Llama"},
            {"id": "Llama-3.2-1B-Instruct", "name": "Llama 3.2 1B", "family": "Meta Llama"},
            # ── Mistral AI ────────────────────────────────────────────────────
            {"id": "Mistral-Large-3", "name": "Mistral Large 3", "family": "Mistral"},
            {"id": "Mistral-medium-2505", "name": "Mistral Medium 25.05", "family": "Mistral"},
            {"id": "Mistral-small-2503", "name": "Mistral Small 25.03", "family": "Mistral"},
            {"id": "Codestral-2501", "name": "Codestral 2501 (code)", "family": "Mistral"},
            {"id": "Ministral-3B", "name": "Ministral 3B", "family": "Mistral"},
            # ── Microsoft Phi ─────────────────────────────────────────────────
            {"id": "Phi-4", "name": "Phi-4", "family": "Microsoft Phi"},
            {"id": "Phi-4-mini-instruct", "name": "Phi-4 Mini", "family": "Microsoft Phi"},
            {
                "id": "Phi-4-multimodal-instruct",
                "name": "Phi-4 Multimodal",
                "family": "Microsoft Phi",
            },
            {"id": "Phi-4-reasoning", "name": "Phi-4 Reasoning", "family": "Microsoft Phi"},
            {
                "id": "Phi-4-mini-reasoning",
                "name": "Phi-4 Mini Reasoning",
                "family": "Microsoft Phi",
            },
            {"id": "MAI-DS-R1", "name": "MAI-DS-R1 (reasoning)", "family": "Microsoft Phi"},
            # ── DeepSeek (hosted by Azure) ────────────────────────────────────
            {
                "id": "DeepSeek-R1-0528",
                "name": "DeepSeek R1 (0528, reasoning)",
                "family": "DeepSeek",
            },
            {"id": "DeepSeek-R1", "name": "DeepSeek R1 (reasoning)", "family": "DeepSeek"},
            {"id": "DeepSeek-V3.2", "name": "DeepSeek V3.2", "family": "DeepSeek"},
            {"id": "DeepSeek-V3.1", "name": "DeepSeek V3.1", "family": "DeepSeek"},
            {"id": "DeepSeek-V3-0324", "name": "DeepSeek V3 (0324)", "family": "DeepSeek"},
            # ── xAI Grok (hosted by Azure) ────────────────────────────────────
            {"id": "grok-4", "name": "Grok 4", "family": "xAI Grok"},
            {"id": "grok-4-fast-reasoning", "name": "Grok 4 Fast Reasoning", "family": "xAI Grok"},
            {"id": "grok-3", "name": "Grok 3", "family": "xAI Grok"},
            {"id": "grok-3-mini", "name": "Grok 3 Mini", "family": "xAI Grok"},
            # ── Cohere ────────────────────────────────────────────────────────
            {"id": "Cohere-command-a", "name": "Cohere Command A", "family": "Cohere"},
            {
                "id": "Cohere-command-r-plus-08-2024",
                "name": "Cohere Command R+ (2024)",
                "family": "Cohere",
            },
            {
                "id": "Cohere-command-r-08-2024",
                "name": "Cohere Command R (2024)",
                "family": "Cohere",
            },
            # ── Moonshot Kimi (hosted by Azure) ───────────────────────────────
            {"id": "Kimi-K2.5", "name": "Kimi K2.5 (reasoning)", "family": "Moonshot"},
            {"id": "Kimi-K2-Thinking", "name": "Kimi K2 Thinking", "family": "Moonshot"},
        ],
    },
    "azure": {
        "name": "Azure OpenAI",
        "description": "Azure-managed OpenAI — uses YOUR custom deployment names; requires AZURE_API_KEY secret",
        "litellm_prefix": "azure/",
        "requires_secret": "AZURE_API_KEY",  # nosec B105
        "deployment_based": True,
        "deployment_prompt": "Enter your Azure OpenAI deployment name (e.g. 'my-gpt4o-deployment')",
    },
    "sagemaker": {
        "name": "AWS SageMaker",
        "description": "SageMaker inference endpoints — uses YOUR endpoint names; no API key needed (IAM)",
        "litellm_prefix": "sagemaker/",
        "requires_secret": None,  # nosec B105
        "deployment_based": True,
        "deployment_prompt": "Enter your SageMaker endpoint name (e.g. 'my-llama-endpoint')",
    },
}


# ── Platform default models ───────────────────────────────────────────────────
# Single source of truth: config/platform.toml (repo root).
# Credentials for these models are managed by Synteles and injected automatically
# at execution time when the agentlet YAML includes `secrets: [default]`.
# Users never need to configure API keys for these models.


def _load_platform_defaults() -> list[dict[str, Any]]:
    # Search upward from this file for config/platform.toml.
    # Works both in the repo (ux/ is the root) and inside Docker (/app is the root).
    needle = Path("config") / "platform.toml"
    search_root = Path(__file__).resolve()
    config_path: Path | None = None
    for parent in search_root.parents:
        candidate = parent / needle
        if candidate.exists():
            config_path = candidate
            break
    if config_path is None:
        config_path = search_root.parents[3] / needle  # keep a useful path in the error
    try:
        with open(config_path, "rb") as f:
            raw: list[dict[str, Any]] = tomllib.load(f).get("model", [])
    except FileNotFoundError:
        raise FileNotFoundError(f"Platform config not found: {config_path}") from None
    except Exception as exc:
        raise ValueError(f"Invalid TOML in platform config ({config_path}): {exc}") from exc
    for entry in raw:
        entry["is_platform_default"] = True
        entry["secret_literal"] = "default"  # nosec B105
    return raw


PLATFORM_DEFAULT_MODELS: list[dict[str, Any]] = _load_platform_defaults()

# Maps keywords in user secret names to provider hints for the chatbot shortlist.
# Used by get_model_options to surface user-configured providers without guessing model IDs.
_SECRET_PROVIDER_HINTS: list[dict[str, Any]] = [
    {
        "keyword": "anthropic",
        "provider": "anthropic",
        "label": "Anthropic Claude",
        "model_id": "claude-sonnet-4-6",
        "default_temperature": 1.0,
    },
    {
        "keyword": "openai",
        "provider": "openai",
        "label": "OpenAI GPT",
        "model_id": "gpt-4.1",
        "default_temperature": 1.0,
    },
    {
        "keyword": "google",
        "provider": "gemini",
        "label": "Google Gemini",
        "model_id": "gemini-2.5-pro",
        "default_temperature": 1.0,
    },
    # azure / bedrock require user-supplied deployment name — model_id left None
    {
        "keyword": "azure",
        "provider": "azure_ai",
        "label": "Azure AI (custom deployment)",
        "model_id": None,
        "default_temperature": 0.7,
    },
    {
        "keyword": "bedrock",
        "provider": "bedrock",
        "label": "AWS Bedrock (custom model)",
        "model_id": None,
        "default_temperature": 0.7,
    },
]


def get_providers_summary() -> list[dict[str, Any]]:
    """Return a concise list of providers for display to users."""
    result = []
    for pid, pdata in PROVIDERS.items():
        entry: dict[str, Any] = {
            "id": pid,
            "name": pdata["name"],
            "description": pdata["description"],
            "deployment_based": pdata.get("deployment_based", False),
        }
        if not pdata.get("deployment_based"):
            entry["models"] = [
                {"id": m["id"], "name": m["name"], "family": m.get("family")}
                for m in pdata.get("models", [])
            ]
        result.append(entry)
    return result


def resolve_model(provider_id: str, model_input: str) -> dict[str, Any]:
    """
    Resolve a provider + model input (number, name, or full ID) into validated YAML values.

    Returns a dict with: provider, model_id, secret_hint, cross_region_note (optional).
    Raises ValueError on unknown provider or model input.
    """
    provider_id = provider_id.strip().lower()
    if provider_id not in PROVIDERS:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(f"Unknown provider '{provider_id}'. Available: {available}")

    pdata = PROVIDERS[provider_id]

    # Deployment-based providers: accept free-text endpoint/deployment name
    if pdata.get("deployment_based"):
        model_id = model_input.strip()
        if not model_id:
            raise ValueError(pdata.get("deployment_prompt", "Please enter a deployment name"))
        secret_hint = (
            f"Requires '{pdata['requires_secret']}' secret"
            if pdata.get("requires_secret")
            else "Uses IAM permissions — no API key secret needed"
        )
        return {"provider": provider_id, "model_id": model_id, "secret_hint": secret_hint}

    # Catalog-based providers: resolve by index, name substring, or exact ID
    models: list[dict[str, Any]] = pdata.get("models", [])
    resolved: dict[str, Any] | None = None

    stripped = model_input.strip()

    # Try numeric index (1-based)
    if stripped.isdigit():
        idx = int(stripped) - 1
        if 0 <= idx < len(models):
            resolved = models[idx]
        else:
            raise ValueError(f"Model number {stripped} out of range (1–{len(models)})")
    else:
        # Exact ID match first
        for m in models:
            if m["id"].lower() == stripped.lower():
                resolved = m
                break
        # Name substring match
        if not resolved:
            lower = stripped.lower()
            matches = [m for m in models if lower in m["id"].lower() or lower in m["name"].lower()]
            if len(matches) == 1:
                resolved = matches[0]
            elif len(matches) > 1:
                names = ", ".join(m["id"] for m in matches)
                raise ValueError(
                    f"Ambiguous model '{stripped}' — matches: {names}. Please be more specific."
                )
            else:
                raise ValueError(f"Model '{stripped}' not found for provider '{provider_id}'")

    if pdata.get("requires_secret"):
        secret_hint = f"Requires '{pdata['requires_secret']}' secret configured on the platform"
    else:
        secret_hint = "Uses IAM permissions — no API key secret needed"  # nosec B105

    result: dict[str, Any] = {
        "provider": provider_id,
        "model_id": resolved["id"],
        "model_name": resolved["name"],
        "secret_hint": secret_hint,
    }

    if "cross_region_profiles" in pdata:
        result["cross_region_note"] = (
            "Optionally prefix with 'us.', 'eu.', or 'global.' for cross-region routing "
            "(e.g. 'us.anthropic.claude-sonnet-4-6')"
        )

    return result


@tool
def get_model_catalog() -> dict[str, Any]:
    """
    Returns the full catalog of supported LLM providers and their available models.

    Use this to present provider/model options to the user during agentlet creation
    or when the user asks which models or providers are available.
    After presenting the options and collecting the user's choice, call
    resolve_model_selection() to validate and format the result.

    Returns:
        A dict with a 'providers' list. Each entry has: id, name, description,
        deployment_based, and (for catalog providers) a 'models' list of
        {id, name, family} dicts.
    """
    return {"providers": get_providers_summary()}


@tool
def resolve_model_selection(provider_id: str, model_input: str) -> dict[str, Any]:
    """
    Validates and resolves the user's provider + model selection into YAML-ready values.

    Call this after the user has chosen a provider and model (or typed a model ID).
    The result contains the exact values to use in the agentlet YAML model section.

    Args:
        provider_id: Provider key string (e.g. 'bedrock', 'anthropic', 'openai',
                     'azure_ai', 'vertex_ai', 'gemini', 'azure', 'sagemaker').
        model_input: The user's selection — a 1-based number from the displayed list,
                     a model name substring, or a full model ID string. For
                     deployment-based providers (azure, sagemaker) this is the
                     deployment/endpoint name the user provided.

    Returns:
        {
            "provider": "<provider_id>",
            "model_id": "<resolved model ID>",
            "model_name": "<human-readable name>",   # omitted for deployment-based
            "secret_hint": "<what secret/IAM is required>",
            "cross_region_note": "<optional Bedrock cross-region guidance>"
        }
        On error returns {"error": "<message>"}.
    """
    try:
        return resolve_model(provider_id, model_input)
    except ValueError as exc:
        return {"error": str(exc)}
