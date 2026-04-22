"""NIM client primitives for Buffa."""

from __future__ import annotations

from buffa.nim.client import BaseNIMClient, NIMError
from buffa.nim.embedding import EmbeddingClient
from buffa.nim.health import auth_preflight, health_check
from buffa.nim.reranking import RerankingClient

__all__ = [
    "BaseNIMClient",
    "NIMError",
    "EmbeddingClient",
    "RerankingClient",
    "auth_preflight",
    "health_check",
]
