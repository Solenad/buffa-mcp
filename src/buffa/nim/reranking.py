"""Typed reranking client."""

from __future__ import annotations

from typing import Literal

from buffa.nim.client import BaseNIMClient, NIMError, NIMErrorCategory
from buffa.nim.config import NimConfig


class RerankingClient(BaseNIMClient):
    """Typed client for NIM reranking endpoint."""

    def __init__(self, config: NimConfig) -> None:
        super().__init__(config, f"{config.base_url}/reranking")

    def rerank(
        self,
        query: str,
        documents: list[str],
        model: str | None = None,
        top_k: int | None = None,
    ) -> list[dict[str, float | int]]:
        """Rerank documents based on relevance to query.
        
        Args:
            query: Search query
            documents: List of documents to rerank
            model: Optional model override (uses config.reranking_model if not provided)
            top_k: Optional number of top results to return
            
        Returns:
            List of dicts with 'index' and 'score' keys, sorted by score descending
            
        Raises:
            NIMError: For various failure categories
        """
        # Prepare request payload
        payload = {
            "query": query,
            "documents": documents,
            "model": model or self.config.reranking_model,
        }
        if top_k is not None:
            payload["top_k"] = top_k

        # Make request
        response = self._request("POST", "", json=payload)
        
        # Extract reranking results from response
        # Expected format: {"results": [{"index": 0, "score": 0.9}, ...]}
        results = response.get("results", [])
        if not results:
            raise NIMError(
                message="No reranking results returned from NIM endpoint",
                category=NIMErrorCategory.RESPONSE_SHAPE,
                retryable=False,
                endpoint=self.endpoint,
            )

        # Validate and sort results by score descending
        validated_results = []
        for i, result in enumerate(results):
            if not isinstance(result, dict) or "index" not in result or "score" not in result:
                raise NIMError(
                    message=f"Invalid result format at index {i}: {result}",
                    category=NIMErrorCategory.RESPONSE_SHAPE,
                    retryable=False,
                    endpoint=self.endpoint,
                )
            validated_results.append({
                "index": int(result["index"]),
                "score": float(result["score"])
            })
        
        # Sort by score descending
        validated_results.sort(key=lambda x: x["score"], reverse=True)
        
        # Apply top_k limit if specified
        if top_k is not None:
            validated_results = validated_results[:top_k]
            
        return validated_results
