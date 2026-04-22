from __future__ import annotations

import pytest

from buffa.config.runtime import load_runtime_settings
from buffa.shared.errors import StartupDiagnosticError


def test_load_runtime_settings_applies_defaults() -> None:
    settings = load_runtime_settings({"NVIDIA_API_KEY": "token"})

    assert settings.nim_api_key == "token"
    assert settings.nim_base_url == "https://integrate.api.nvidia.com/v1"
    assert settings.config_path == ".buffa.json"
    assert settings.log_level == "INFO"


def test_load_runtime_settings_requires_api_key() -> None:
    with pytest.raises(StartupDiagnosticError) as exc:
        load_runtime_settings({})

    assert "NVIDIA_API_KEY" in str(exc.value)


def test_load_runtime_settings_rejects_empty_optional_values() -> None:
    with pytest.raises(StartupDiagnosticError) as exc:
        load_runtime_settings(
            {
                "NVIDIA_API_KEY": "token",
                "BUFFA_LOG_LEVEL": "   ",
            }
        )

    assert "BUFFA_LOG_LEVEL" in str(exc.value)
