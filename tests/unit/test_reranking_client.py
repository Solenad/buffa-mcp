from __future__ import annotations

from unittest import mock

import pytest

from buffa.nim.reranking import RerankingClient
from buffa.nim.config import NimConfig as NIMNimConfig
from buffa.nim.client import NIMError, NIMErrorCategory


def test_reranking_client_basic() -> None:
    config = NIMNimConfig()
    client = RerankingClient(config)
    
    with mock.patch.object(client, '_request') as mock_request:
        mock_request.return_value = {
            "results": [
                {"index": 1, "score": 0.9},
                {"index": 0, "score": 0.7},
                {"index": 2, "score": 0.5}
            ]
        }
        
        result = client.rerank("test query", ["doc0", "doc1", "doc2"])
        
        # Check that results are sorted by score descending
        assert len(result) == 3
        assert result[0]["index"] == 1
        assert result[0]["score"] == 0.9
        assert result[1]["index"] == 0
        assert result[1]["score"] == 0.7
        assert result[2]["index"] == 2
        assert result[2]["score"] == 0.5


def test_reranking_client_with_model_override() -> None:
    config = NIMNimConfig()
    client = RerankingClient(config)
    
    with mock.patch.object(client, '_request') as mock_request:
        mock_request.return_value = {
            "results": [{"index": 0, "score": 0.8}]
        }
        
        result = client.rerank("test", ["single doc"], model="custom-model")
        
        args, kwargs = mock_request.call_args
        json_payload = kwargs["json"]
        assert json_payload["model"] == "custom-model"
        assert result == [{"index": 0, "score": 0.8}]


def test_reranking_client_with_top_k() -> None:
    config = NIMNimConfig()
    client = RerankingClient(config)
    
    with mock.patch.object(client, '_request') as mock_request:
        mock_request.return_value = {
            "results": [
                {"index": 0, "score": 0.9},
                {"index": 1, "score": 0.8},
                {"index": 2, "score": 0.7},
                {"index": 3, "score": 0.6}
            ]
        }
        
        result = client.rerank("test", ["doc0", "doc1", "doc2", "doc3"], top_k=2)
        
        # Should only return top 2 results
        assert len(result) == 2
        assert result[0]["index"] == 0
        assert result[0]["score"] == 0.9
        assert result[1]["index"] == 1
        assert result[1]["score"] == 0.8


def test_reranking_client_handles_empty_results() -> None:
    config = NIMNimConfig()
    client = RerankingClient(config)
    
    with mock.patch.object(client, '_request') as mock_request:
        mock_request.return_value = {"results": []}
        
        with pytest.raises(NIMError) as exc_info:
            client.rerank("test", ["doc"])
        
        assert exc_info.value.category == NIMErrorCategory.RESPONSE_SHAPE
        assert "No reranking results" in str(exc_info.value)


def test_reranking_client_handles_invalid_result_format() -> None:
    config = NIMNimConfig()
    client = RerankingClient(config)
    
    with mock.patch.object(client, '_request') as mock_request:
        mock_request.return_value = {
            "results": [{"index": 0}]  # Missing "score" field
        }
        
        with pytest.raises(NIMError) as exc_info:
            client.rerank("test", ["doc"])
        
        assert exc_info.value.category == NIMErrorCategory.RESPONSE_SHAPE
        assert "Invalid result format" in str(exc_info.value)
