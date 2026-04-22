"""Configuration loader for Buffa."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from buffa.config.models import BuffaConfig
from buffa.shared.errors import StartupDiagnosticError


def load_config(config_path: str | Path) -> BuffaConfig:
    """Load and validate Buffa configuration from .buffa.json.

    Handles:
    - Default values when file is missing
    - Environment variable expansion in format ${VAR_NAME}
    - Required secret enforcement (raises on missing env vars)
    - JSON parsing with helpful error messages
    - Pydantic validation of the final configuration

    Args:
        config_path: Path to the .buffa.json file

    Returns:
        Validated BuffaConfig instance

    Raises:
        StartupDiagnosticError: For missing required env vars or invalid JSON
    """
    path = Path(config_path)

    # If file doesn't exist, return defaults
    if not path.exists():
        return BuffaConfig()

    # Read and parse JSON
    try:
        raw_content = path.read_text(encoding="utf-8")
        config_data: dict[str, Any] = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise StartupDiagnosticError(
            f"Failed to parse {path}: {exc.msg}") from exc

    # Expand environment variables in string values
    expanded_data = _expand_env_vars(config_data)

    # Validate with Pydantic
    try:
        return BuffaConfig(**expanded_data)
    except Exception as exc:
        raise StartupDiagnosticError(f"Invalid configuration in {
                                     path}: {exc}") from exc


def _expand_env_vars(data: Any) -> Any:
    """Recursively expand environment variables in strings.

    Looks for patterns like ${VAR_NAME} and
    replaces them with os.environ[VAR_NAME].
    Raises StartupDiagnosticError if a variable is missing.
    """
    if isinstance(data, str):
        # Find all ${VAR_NAME} patterns
        matches = re.findall(r"\$\{([^}]+)\}", data)
        if not matches:
            return data

        # Replace each match with environment variable value
        result = data
        for var_name in matches:
            if var_name not in os.environ:
                raise StartupDiagnosticError(
                    f"Missing required environment variable: {var_name}"
                )
            value = os.environ[var_name]
            result = result.replace(f"${{{var_name}}}", value)
        return result

    elif isinstance(data, dict):
        return {key: _expand_env_vars(value) for key, value in data.items()}

    elif isinstance(data, list):
        return [_expand_env_vars(item) for item in data]

    else:
        # Numbers, booleans, None - return as-is
        return data
