from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

import pytest

from buffa.config.loader import load_config
from buffa.shared.errors import StartupDiagnosticError


def test_load_config_uses_defaults_if_file_missing(tmp_path: Path) -> None:
    config_path = tmp_path / ".buffa.json"
    # File does not exist
    config = load_config(config_path)
    
    assert config.nim.embedding_model == "nvidia/nv-embedqa-e5-v5"
    assert config.token_budget.default_reserve == 512


def test_load_config_parses_valid_json(tmp_path: Path) -> None:
    config_path = tmp_path / ".buffa.json"
    config_data = {
        "nim": {
            "embedding_model": "custom-model"
        },
        "token_budget": {
            "default_reserve": 1024
        }
    }
    config_path.write_text(json.dumps(config_data))
    
    config = load_config(config_path)
    assert config.nim.embedding_model == "custom-model"
    assert config.token_budget.default_reserve == 1024


def test_load_config_expands_env_vars(tmp_path: Path) -> None:
    config_path = tmp_path / ".buffa.json"
    config_data = {
        "nim": {
            "embedding_model": "${MY_MODEL_VAR}"
        }
    }
    config_path.write_text(json.dumps(config_data))
    
    with mock.patch.dict(os.environ, {"MY_MODEL_VAR": "env-model"}):
        config = load_config(config_path)
    
    assert config.nim.embedding_model == "env-model"


def test_load_config_fails_on_missing_env_var(tmp_path: Path) -> None:
    config_path = tmp_path / ".buffa.json"
    config_data = {
        "nim": {
            "embedding_model": "${MISSING_VAR}"
        }
    }
    config_path.write_text(json.dumps(config_data))
    
    with mock.patch.dict(os.environ, {}, clear=True):
        with pytest.raises(StartupDiagnosticError) as exc:
            load_config(config_path)
    
    assert "MISSING_VAR" in str(exc.value)


def test_load_config_fails_on_invalid_json(tmp_path: Path) -> None:
    config_path = tmp_path / ".buffa.json"
    config_path.write_text("{ invalid json")
    
    with pytest.raises(StartupDiagnosticError) as exc:
        load_config(config_path)
    
    assert "Failed to parse" in str(exc.value)
