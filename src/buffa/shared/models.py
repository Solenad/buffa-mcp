"""Shared data models for Buffa."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ChunkMetadata:
    """Metadata for a source code chunk."""
    file_path: str
    language: str
    symbol_type: str  # function, class, method, interface, impl, block, fallback
    start_line: int
    end_line: int
    symbol_name: str
    hash: Optional[str] = None  # Content hash for incremental indexing
    raw_token_estimate: Optional[int] = None
    compressed_token_estimate: Optional[int] = None


@dataclass
class SourceChunk:
    """A chunk of source code with associated metadata."""
    content: str
    metadata: ChunkMetadata