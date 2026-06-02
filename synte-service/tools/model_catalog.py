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
Platform default models for the Synteles Platform.

No API calls — always available. Loaded from config/platform.toml.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

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
