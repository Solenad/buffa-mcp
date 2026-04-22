"""Runtime environment contract and startup diagnostics."""

from __future__ import annotations

import os
from dataclasses import dataclass

from buffa.shared.errors import StartupDiagnosticError


@dataclass(frozen=True)
class RuntimeSettings:
    """Resolved runtime settings for bootstrap-stage Buffa execution."""

    nim_api_key: str
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    config_path: str = ".buffa.json"
    log_level: str = "INFO"


def load_runtime_settings(env: dict[str, str] | None = None) -> RuntimeSettings:
    """Load required and optional runtime settings from environment."""

    source = env or os.environ
    nim_api_key = source.get("NVIDIA_API_KEY", "").strip()
    if not nim_api_key:
        raise StartupDiagnosticError(
            "Missing required environment variable: NVIDIA_API_KEY"
        )

    nim_base_url = source.get("BUFFA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    config_path = source.get("BUFFA_CONFIG_PATH", ".buffa.json")
    log_level = source.get("BUFFA_LOG_LEVEL", "INFO")

    if not nim_base_url.strip():
        raise StartupDiagnosticError("Invalid BUFFA_NIM_BASE_URL: value cannot be empty")

    if not config_path.strip():
        raise StartupDiagnosticError("Invalid BUFFA_CONFIG_PATH: value cannot be empty")

    if not log_level.strip():
        raise StartupDiagnosticError("Invalid BUFFA_LOG_LEVEL: value cannot be empty")

    return RuntimeSettings(
        nim_api_key=nim_api_key,
        nim_base_url=nim_base_url,
        config_path=config_path,
        log_level=log_level.upper(),
    )
