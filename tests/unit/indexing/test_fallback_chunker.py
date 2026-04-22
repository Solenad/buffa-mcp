"""Tests for fallback text chunker."""

from __future__ import annotations

import pytest
from buffa.indexing.fallback_chunker import FallbackChunker, ChunkingResult
from buffa.shared.models import SourceChunk, ChunkMetadata


def test_fallback_chunker_initialization():
    """Test that FallbackChunker initializes correctly."""
    chunker = FallbackChunker()
    assert chunker is not None


def test_fallback_chunking_basic():
    """Test basic fallback chunking."""
    chunker = FallbackChunker()
    content = "line 1\nline 2\nline 3\nline 4\nline 5"
    result = chunker.chunk_content(content, "test.txt")
    
    assert isinstance(result, ChunkingResult)
    assert len(result.chunks) > 0
    assert result.method_used == "fallback"
    assert 0.0 <= result.confidence <= 1.0


def test_fallback_chunking_with_overlap():
    """Test fallback chunking respects line boundaries reasonably."""
    chunker = FallbackChunker()
    # Create content that should produce multiple chunks
    lines = [f"line {i}" for i in range(50)]  # 50 lines
    content = "\n".join(lines)
    
    result = chunker.chunk_content(content, "test.txt")
    
    # Should have multiple chunks due to line limit
    assert len(result.chunks) > 1
    
    # Each chunk should have content
    for chunk in result.chunks:
        assert chunk.content.strip()
        assert chunk.metadata.symbol_type == "fallback"


def test_chunking_result_properties():
    """Test ChunkingResult properties."""
    chunks = [
        SourceChunk(
            content="test",
            metadata=ChunkMetadata(
                file_path="test.py",
                language="python",
                symbol_type="function",
                start_line=1,
                end_line=1,
                symbol_name="test"
            )
        )
    ]
    
    result = ChunkingResult(
        chunks=chunks,
        confidence=0.8,
        method_used="fallback",
        parser_available=False
    )
    
    assert len(result.chunks) == 1
    assert result.confidence == 0.8
    assert result.method_used == "fallback"
    assert result.parser_available is False