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

"""Agentlet YAML validation tool for the Synteles Platform chat agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import jsonschema
import yaml
from strands import tool

# Schema lives at the service root (services/chat-stream/agentlet-schema.json)
_SCHEMA_PATH = Path(__file__).parent.parent / "agentlet-schema.json"


def _strip_code_fences(content: str) -> str:
    """Remove markdown YAML/code fences if present."""
    lines = content.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


def _load_schema() -> dict[Any, Any]:
    with open(_SCHEMA_PATH) as f:
        return cast(dict[Any, Any], json.load(f))


def validate_yaml(content: str) -> str:
    """Pure validation function — no Strands dependency.

    Returns a string starting with "VALID" on success, or "INVALID - ..."
    describing every issue found.
    """
    cleaned = _strip_code_fences(content)

    try:
        data = yaml.safe_load(cleaned)
    except yaml.YAMLError as exc:
        return f"INVALID - YAML syntax error: {exc}\n\nFix the YAML syntax and regenerate."

    if not isinstance(data, dict):
        return (
            "INVALID - YAML must be a mapping object. "
            "Expected top-level keys: agentlet, system_prompt, model."
        )

    try:
        schema = _load_schema()
        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    except Exception as exc:
        return f"INVALID - Could not load validation schema: {exc}"

    if not errors:
        return "VALID - Agentlet YAML is valid and ready to deploy."

    lines = [f"INVALID - {len(errors)} schema validation error(s) found:\n"]
    for i, err in enumerate(errors, 1):
        path = " -> ".join(str(p) for p in err.absolute_path) or "(root)"
        lines.append(f"  {i}. Field '{path}': {err.message}")

    lines.append("\nPlease fix the above issues and regenerate the YAML definition.")
    return "\n".join(lines)


@tool
def validate_agentlet(yaml_content: str) -> str:
    """Validate an agentlet YAML definition against the Synteles schema.

    Checks both YAML syntax and conformance to the agentlet JSON Schema
    (required fields, value types, enum constraints, etc.).

    Call this tool after ``agent_creator_assistant`` returns a YAML definition
    and before calling ``synteles_create_agentlet`` or ``synteles_update_agentlet``.
    If the result starts with "INVALID", pass the error details back to
    ``agent_creator_assistant`` and ask it to fix the specific issues.

    Args:
        yaml_content: The YAML string to validate. Markdown code fences
                      (```yaml ... ```) are stripped automatically.

    Returns:
        A string starting with "VALID" if the definition passes all checks,
        or "INVALID - <detailed error list>" describing every issue found.
    """
    return validate_yaml(yaml_content)
