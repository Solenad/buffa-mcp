from __future__ import annotations

from unittest import mock

import json
import pytest

import httpx

from buffa.nim.embedding import EmbeddingClient
from buffa.nim.config import NimConfig as NIMNimConfig
from buffa.nim.client import NIMError, NIMErrorCategory


def test_embedding_client_handles_timeout() -> None:
    """Test that timeout errors are properly categorized."""
    config = NIMNimConfig()
    client = EmbeddingClient(config)
    
    with mock.patch.object(client.client, 'request') as mock_request:
        mock_request.side_effect = httpx.TimeoutException("Request timed out")
        
        with pytest.raises(NIMError) as exc_info:
            client.embed("test")
        
        assert exc_info.value.category == NIMErrorCategory.TIMEOUT
        assert exc_info.value.retryable is True
        assert "timed out" in str(exc_info.value)


def test_embedding_client_handles_network_error() -> None:
    """Test that network errors are properly categorized."""
    config = NIMNimConfig()
    client = EmbeddingClient(config)
    
    with mock.patch.object(client.client, 'request') as mock_request:
        mock_request.side_effect = httpx.NetworkError("Network error")
        
        with pytest.raises(NIMError) as exc_info:
            client.embed("test")
        
        assert exc_info.value.category == NIMErrorCategory.TRANSPORT
        assert exc_info.value.retryable is True
        assert "Network error" in str(exc_info.value)


def test_embedding_client_handles_http_401() -> None:
    """Test that HTTP 401 errors are properly categorized as auth errors."""
    config = NIMNimConfig()
    client = EmbeddingClient(config)
    
    # Mock the underlying HTTP client to simulate a 401 response
    with mock.patch.object(client.client, 'request') as mock_request:
        # Create a mock response that raises the appropriate NIMError in _handle_response
        def mock_handle_response(response):
            if response.status_code == 401:
                raise NIMError(
                    message="Authentication failed with NIM endpoint",
                    category=NIMErrorCategory.AUTH,
                    retryable=False,
                    endpoint=client.endpoint,
                    request_id=response.headers.get("x-nvidia-request-id"),
                )
            # For other status codes, return some data so we can reach the JSON parsing
            return {"data": [{"embedding": [0.1, 0.2], "index": 0}]}
        
        with mock.patch.object(client, '_handle_response', side_effect=mock_handle_response):
            mock_request.return_value = mock.Mock()
            mock_request.return_value.status_code = 401
            mock_request.return_value.headers = {}
            
            with pytest.raises(NIMError) as exc_info:
                client.embed("test")
            
            assert exc_info.value.category == NIMErrorCategory.AUTH
            assert exc_info.value.retryable is False
            assert "Authentication failed" in str(exc_info.value)


def test_embedding_client_handles_http_500() -> None:
    """Test that HTTP 500 errors are properly categorized as transport errors."""
    config = NIMNimConfig()
    client = EmbeddingClient(config)
    
    # Mock the underlying HTTP client to simulate a 500 response
    with mock.patch.object(client.client, 'request') as mock_request:
        # Create a mock response that raises the appropriate NIMError in _handle_response
        def mock_handle_response(response):
            if response.status_code >= 500:
                raise NIMError(
                    message=f"NIM endpoint server error: {response.status_code}",
                    category=NIMErrorCategory.TRANSPORT,
                    retryable=True,
                    endpoint=client.endpoint,
                    request_id=response.headers.get("x-nvidia-request-id"),
                )
            # For other status codes, return some data so we can reach the JSON parsing
            return {"data": [{"embedding": [0.1, 0.2], "index": 0}]}
        
        with mock.patch.object(client, '_handle_response', side_effect=mock_handle_response):
            mock_request.return_value = mock.Mock()
            mock_request.return_value.status_code = 500
            mock_request.return_value.headers = {}
            
            with pytest.raises(NIMError) as exc_info:
                client.embed("test")
            
            assert exc_info.value.category == NIMErrorCategory.TRANSPORT
            assert exc_info.value.retryable is True
            assert "NIM endpoint server error: 500" in str(exc_info.value)


def test_embedding_client_handles_invalid_json() -> None:
    """Test that invalid JSON responses are properly categorized."""
    config = NIMNimConfig()
    client = EmbeddingClient(config)
    
    with mock.patch.object(client, '_handle_response') as mock_handle:
        # Simulate the actual error that would be raised in _handle_response
        mock_handle.side_effect = NIMError(
            message="Failed to parse NIM response as JSON: Expecting value",
            category=NIMErrorCategory.RESPONSE_SHAPE,
            retryable=False
        )
        
        with pytest.raises(NIMError) as exc_info:
            client.embed("test")
        
        assert exc_info.value.category == NIMErrorCategory.RESPONSE_SHAPE
        assert exc_info.value.retryable is False
        assert "Failed to parse NIM response as JSON" in str(exc_info.value)


def test_embedding_client_handles_empty_embedding_data() -> None:
    """Test that empty embedding data is properly categorized as response shape error."""
    config = NIMNimConfig()
    client = EmbeddingClient(config)
    
    with mock.patch.object(client, '_request') as mock_request:
        mock_request.return_value = {"data": []}
        
        with pytest.raises(NIMError) as exc_info:
            client.embed("test")
        
        assert exc_info.value.category == NIMErrorCategory.RESPONSE_SHAPE
        assert exc_info.value.retryable is False
        assert "No embedding data returned" in str(exc_info.value)


def test_embedding_client_successful_request() -> None:
    """Test that successful requests work correctly."""
    config = NIMNimConfig()
    client = EmbeddingClient(config)
    
    with mock.patch.object(client, '_request') as mock_request:
        mock_request.return_value = {
            "data": [
                {"embedding": [0.1, 0.2, 0.3], "index": 0},
                {"embedding": [0.4, 0.5, 0.6], "index": 1}
            ]
        }
        
        result = client.embed(["hello", "world"], input_type="passage")
        
        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        # Verify the request was made with correct parameters
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert args[0] == "POST"
        assert args[1] == ""
        json_payload = kwargs["json"]
        assert json_payload["input"] == ["hello", "world"]
        assert json_payload["input_type"] == "passage"
