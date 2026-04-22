"""Typed embedding client with input_type support."""

from __future__ import annotations

from typing import Literal

from buffa.nim.client import BaseNIMClient, NIMError, NIMErrorCategory
from buffa.nim.config import NimConfig


class EmbeddingClient(BaseNIMClient):
    """Typed client for NIM embedding endpoint with input_type support."""

    def __init__(self, config: NimConfig) -> None:
        super().__init__(config, f"{config.base_url}/embeddings")

    def embed(
        self,
        text: str | list[str],
        input_type: Literal["query", "passage"] = "passage",
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for text with specified input_type.
        
        Args:
            text: Single string or list of strings to embed
            input_type: Either "query" for search queries or "passage" for documents
            model: Optional model override (uses config.embedding_model if not provided)
            
        Returns:
            List of embedding vectors (one per input text)
            
        Raises:
            NIMError: For various failure categories
        """
        # Prepare request payload
        payload = {
            "input": text if isinstance(text, list) else [text],
            "model": model or self.config.embedding_model,
            "input_type": input_type,
        }

        # Make request
        response = self._request("POST", "", json=payload)
        
        # Extract embeddings from response
        # Expected format: {"data": [{"embedding": [...], "index": 0}, ...]}
        embeddings_data = response.get("data", [])
        if not embeddings_data:
            raise NIMError(
                message="No embedding data returned from NIM endpoint",
                category=NIMErrorCategory.RESPONSE_SHAPE,
                retryable=False,
                endpoint=self.endpoint,
            )

        # Sort by index to maintain order and extract embeddings
        embeddings_data.sort(key=lambda x: x.get("index", 0))
        embeddings = [item["embedding"] for item in embeddings_data]
        
        return embeddings
