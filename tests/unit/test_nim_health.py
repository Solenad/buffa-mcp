from __future__ import annotations

from unittest import mock

import pytest

from buffa.nim.health import auth_preflight, health_check
from buffa.nim.config import NimConfig as NIMNimConfig


def test_health_check_success() -> None:
    config = NIMNimConfig()
    
    with mock.patch("buffa.nim.health.BaseNIMClient") as mock_client_class:
        mock_client = mock.Mock()
        mock_client_class.return_value = mock_client
        mock_client.client.get.return_value.is_success = True
        
        result = health_check(config)
        
        assert result is True
        mock_client_class.assert_called_once_with(config, f"{config.base_url}/health")
        mock_client.client.get.assert_called_once_with("", timeout=5.0)
        mock_client.close.assert_called_once()


def test_health_check_failure() -> None:
    config = NIMNimConfig()
    
    with mock.patch("buffa.nim.health.BaseNIMClient") as mock_client_class:
        mock_client = mock.Mock()
        mock_client_class.return_value = mock_client
        mock_client.client.get.return_value.is_success = False
        
        result = health_check(config)
        
        assert result is False
        mock_client.close.assert_called_once()


def test_health_check_exception() -> None:
    config = NIMNimConfig()
    
    with mock.patch("buffa.nim.health.BaseNIMClient") as mock_client_class:
        mock_client = mock.Mock()
        mock_client_class.return_value = mock_client
        mock_client.client.get.side_effect = Exception("Network error")
        
        result = health_check(config)
        
        assert result is False
        mock_client.close.assert_called_once()


def test_auth_preflight_valid_config() -> None:
    config = NIMNimConfig()
    # This should pass with default valid config
    result = auth_preflight(config)
    assert result is True


def test_auth_preflight_missing_base_url() -> None:
    config = NIMNimConfig(base_url="")
    result = auth_preflight(config)
    assert result is False


def test_auth_preflight_missing_embedding_model() -> None:
    config = NIMNimConfig(embedding_model="")
    result = auth_preflight(config)
    assert result is False
