from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from buffa.config.loader import load_config
from buffa.config.models import BuffaConfig
from buffa.shared.errors import StartupDiagnosticError


def test_config_valid_file_loads_successfully(tmp_path: Path) -> None:
    """Test that a valid .buffa.json file loads successfully."""
    config_path = tmp_path / ".buffa.json"
    config_data = {
        "nim": {
            "embedding_model": "test/embedding-model",
            "reranking_model": "test/reranking-model",
            "timeout_seconds": 60
        },
        "token_budget": {
            "per_model_overrides": {
                "test-model": 2048
            },
            "default_reserve": 128
        }
    }
    config_path.write_text(json.dumps(config_data))
    
    config = load_config(config_path)
    
    assert isinstance(config, BuffaConfig)
    assert config.nim.embedding_model == "test/embedding-model"
    assert config.nim.reranking_model == "test/reranking-model"
    assert config.nim.timeout_seconds == 60
    assert config.token_budget.per_model_overrides["test-model"] == 2048
    assert config.token_budget.default_reserve == 128


def test_config_missing_file_uses_defaults(tmp_path: Path) -> None:
    """Test that missing config file uses default values."""
    config_path = tmp_path / ".buffa.json"
    # File does not exist
    
    config = load_config(config_path)
    
    assert isinstance(config, BuffaConfig)
    # Should use defaults
    assert config.nim.embedding_model == "nvidia/nv-embedqa-e5-v5"
    assert config.nim.reranking_model == "nvidia/nv-rerankqa-mistral-4b-v3"
    assert config.nim.timeout_seconds == 30
    assert config.token_budget.per_model_overrides == {}
    assert config.token_budget.default_reserve == 512


def test_config_invalid_json_raises_error(tmp_path: Path) -> None:
    """Test that invalid JSON raises StartupDiagnosticError."""
    config_path = tmp_path / ".buffa.json"
    config_path.write_text("{ invalid json content")
    
    with pytest.raises(StartupDiagnosticError) as exc_info:
        load_config(config_path)
    
    assert "Failed to parse" in str(exc_info.value)


def test_config_missing_required_env_var_raises_error(tmp_path: Path) -> None:
    """Test that missing required environment variable raises error."""
    config_path = tmp_path / ".buffa.json"
    config_data = {
        "nim": {
            "embedding_model": "${MISSING_ENV_VAR}"
        }
    }
    config_path.write_text(json.dumps(config_data))
    
    with mock.patch.dict("os.environ", {}, clear=True):
        with pytest.raises(StartupDiagnosticError) as exc_info:
            load_config(config_path)
    
    assert "MISSING_ENV_VAR" in str(exc_info.value)


def test_config_env_var_expansion_works(tmp_path: Path) -> None:
    """Test that environment variable expansion works correctly."""
    config_path = tmp_path / ".buffa.json"
    config_data = {
        "nim": {
            "embedding_model": "${EMBEDDING_MODEL}",
            "reranking_model": "${RERANKING_MODEL}"
        }
    }
    config_path.write_text(json.dumps(config_data))
    
    with mock.patch.dict("os.environ", {
        "EMBEDDING_MODEL": "custom/embed-model",
        "RERANKING_MODEL": "custom/rerank-model"
    }):
        config = load_config(config_path)
    
    assert config.nim.embedding_model == "custom/embed-model"
    assert config.nim.reranking_model == "custom/rerank-model"


def test_token_budget_resolver_edge_cases() -> None:
    """Test token budget resolver edge cases."""
    # Test with zero reserve
    config = BuffaConfig(
        token_budget=BuffaConfig().token_budget.model_copy(
            update={"default_reserve": 0}
        )
    )
    effective = config.token_budget.get_effective_budget(request_budget=1024)
    assert effective == 1024
    
    # Test with reserve equal to request budget (should fail)
    config = BuffaConfig(
        token_budget=BuffaConfig().token_budget.model_copy(
            update={"default_reserve": 1024}
        )
    )
    with pytest.raises(ValueError, match="non-positive"):
        config.token_budget.get_effective_budget(request_budget=1024)
    
    # Test with reserve greater than request budget (should fail)
    config = BuffaConfig(
        token_budget=BuffaConfig().token_budget.model_copy(
            update={"default_reserve": 2048}
        )
    )
    with pytest.raises(ValueError, match="non-positive"):
        config.token_budget.get_effective_budget(request_budget=1024)
    
    # Test model override works
    config = BuffaConfig(
        token_budget=BuffaConfig().token_budget.model_copy(
            update={
                "per_model_overrides": {"special-model": 512},
                "default_reserve": 128
            }
        )
    )
    effective = config.token_budget.get_effective_budget(
        request_budget=2048,  # Should be ignored
        model="special-model"
    )
    assert effective == 512 - 128  # 384
    
    # Test fallback to request budget when model not in overrides
    effective = config.token_budget.get_effective_budget(
        request_budget=1024,
        model="unknown-model"
    )
    assert effective == 1024 - 128  # 896
