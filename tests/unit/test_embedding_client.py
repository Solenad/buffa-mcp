from __future__ import annotations

from unittest import mock

import pytest

from buffa.nim.embedding import EmbeddingClient
from buffa.nim.config import NimConfig as NIMNimConfig
from buffa.nim.client import NIMError, NIMErrorCategory


def test_embedding_client_uses_query_input_type() -> None:
    config = NIMNimConfig()
    client = EmbeddingClient(config)
    
    with mock.patch.object(client, '_request') as mock_request:
        mock_request.return_value = {
            "data": [{"embedding": [0.1, 0.2], "index": 0}]
        }
        
        result = client.embed("test query", input_type="query")
        
        # Check that the request was made with correct input_type
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        assert args[0] == "POST"  # method
        assert args[1] == ""      # path
        json_payload = kwargs["json"]
        assert json_payload["input_type"] == "query"
        assert json_payload["input"] == ["test query"]
        assert result == [[0.1, 0.2]]


def test_embedding_client_uses_passage_input_type_by_default() -> None:
    config = NIMNimConfig()
    client = EmbeddingClient(config)
    
    with mock.patch.object(client, '_request') as mock_request:
        mock_request.return_value = {
            "data": [{"embedding": [0.3, 0.4], "index": 0}]
        }
        
        result = client.embed("test passage")  # No input_type specified
        
        # Should default to "passage"
        args, kwargs = mock_request.call_args
        json_payload = kwargs["json"]
        assert json_payload["input_type"] == "passage"
        assert result == [[0.3, 0.4]]


def test_embedding_client_handles_multiple_texts() -> None:
    config = NIMNimConfig()
    client = EmbeddingClient(config)
    
    with mock.patch.object(client, '_request') as mock_request:
        mock_request.return_value = {
            "data": [
                {"embedding": [0.1, 0.2], "index": 0},
                {"embedding": [0.3, 0.4], "index": 1}
            ]
        }
        
        result = client.embed(["first", "second"], input_type="passage")
        
        args, kwargs = mock_request.call_args
        json_payload = kwargs["json"]
        assert json_payload["input"] == ["first", "second"]
        assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embedding_client_allows_model_override() -> None:
    config = NIMNimConfig()
    client = EmbeddingClient(config)
    
    with mock.patch.object(client, '_request') as mock_request:
        mock_request.return_value = {
            "data": [{"embedding": [0.5, 0.6], "index": 0}]
        }
        
        result = client.embed("test", model="custom-model")
        
        args, kwargs = mock_request.call_args
        json_payload = kwargs["json"]
        assert json_payload["model"] == "custom-model"
        assert result == [[0.5, 0.6]]


def test_embedding_client_handles_empty_response() -> None:
    config = NIMNimConfig()
    client = EmbeddingClient(config)
    
    with mock.patch.object(client, '_request') as mock_request:
        mock_request.return_value = {"data": []}
        
        with pytest.raises(NIMError) as exc_info:
            client.embed("test")
        
        assert exc_info.value.category == NIMErrorCategory.RESPONSE_SHAPE
        assert "No embedding data" in str(exc_info.value)


def test_embedding_client_handles_missing_embedding_field() -> None:
    config = NIMNimConfig()
    client = EmbeddingClient(config)
    
    with mock.patch.object(client, '_request') as mock_request:
        mock_request.return_value = {
            "data": [{"index": 0}]  # Missing "embedding" field
        }
        
        with pytest.raises(KeyError):  # Will raise KeyError before our NIMError handling
            client.embed("test")
