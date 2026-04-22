"""NIM-specific configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NimConfig(BaseModel):
    """Configuration for NIM endpoint connectivity."""

    embedding_model: str = Field(
        default="nvidia/nv-embedqa-e5-v5",
        description="NIM model to use for embeddings.",
    )
    reranking_model: str = Field(
        default="nvidia/nv-rerankqa-mistral-4b-v3",
        description="NIM model to use for reranking.",
    )
    generation_model: str = Field(
        default="nvidia/nemotron-3-8b-instruct",
        description="NIM model to use for text generation.",
    )
    base_url: str = Field(
        default="https://integrate.api.nvidia.com/v1",
        description="Base URL for NIM endpoints.",
    )
    timeout_seconds: int = Field(
        default=30,
        description="Timeout for NIM endpoint requests.",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts for failed requests.",
    )
